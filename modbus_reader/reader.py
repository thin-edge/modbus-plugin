#!/usr/bin/env python3
import argparse
import json
import logging
import os.path
import sched
import sys
import threading
import time

import tomli
from paho.mqtt import client as mqtt_client
from pymodbus.client.tcp import ModbusTcpClient
from pymodbus.exceptions import ConnectionException
from watchdog.events import FileSystemEventHandler, DirModifiedEvent, FileModifiedEvent
from watchdog.observers import Observer

from .banner import BANNER
from .mapper import MappedMessage, ModbusMapper
from .smartresttemplates import SMARTREST_TEMPLATES

defaultFileDir = "/etc/tedge/plugins/modbus"
baseConfigName = "modbus.toml"
devicesConfigName = "devices.toml"


class ModbusPoll:
    class ConfigFileChangedHandler(FileSystemEventHandler):
        poller = None

        def __init__(self, poller):
            self.poller = poller

        def on_modified(self, event):
            if isinstance(event, DirModifiedEvent):
                return
            if isinstance(event, FileModifiedEvent) and event.event_type == "modified":
                filename = os.path.basename(event.src_path)
                if filename in [baseConfigName, devicesConfigName]:
                    self.poller.reread_config()

    logger: logging.Logger
    tedgeClient: mqtt_client.Client = None
    poll_scheduler = sched.scheduler(time.time, time.sleep)
    baseconfig = {}
    devices = []
    configdir = "."

    def __init__(self, configdir=".", logfile=None):
        self.configdir = configdir
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        if logfile is not None:
            fh = logging.FileHandler(logfile)
            fh.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )
            self.logger.addHandler(fh)
        self.print_banner()

    def reread_config(self):
        self.logger.info("file change detected, reading files")
        newbaseconfig = self.readbasedefinition(f"{self.configdir}/{baseConfigName}")
        restartrequired = False
        if len(newbaseconfig) > 1 and newbaseconfig != self.baseconfig:
            restartrequired = True
            self.baseconfig = newbaseconfig
        newdevices = self.readdevicedefinition(f"{self.configdir}/{devicesConfigName}")
        if (
            len(newdevices) >= 1
            and newdevices.get("device")
            and newdevices.get("device") is not None
            and newdevices.get("device") != self.devices
        ):
            restartrequired = True
            self.devices = newdevices["device"]
        if restartrequired:
            self.logger.info("config change detected, restart polling")
            if self.tedgeClient is not None and self.tedgeClient.is_connected():
                self.tedgeClient.disconnect()
            self.tedgeClient = self.connect_to_thinedge()
            # If connected to tedge, register service, update config and send smart rest template
            time.sleep(5)
            self.registerChildDevices(self.devices)
            self.registerService()
            self.send_smartrest_templates()
            self.updateBaseConfigOnDevice(self.baseconfig)
            self.updateModbusInfoOnChildDevices(self.devices)
            for evt in self.poll_scheduler.queue:
                self.poll_scheduler.cancel(evt)
            self.polldata()

    def watchConfigFiles(self, configDir):
        event_handler = self.ConfigFileChangedHandler(self)
        observer = Observer()
        observer.schedule(event_handler, configDir)
        observer.start()
        try:
            while True:
                time.sleep(5)
        except:
            observer.stop()
            self.logger.error("File observer failed")

    def print_banner(self):
        self.logger.info(BANNER)
        self.logger.info("Author:        Rina,Mario,Murat")
        self.logger.info("Date:          12th October 2022")
        self.logger.info(
            "Description:   "
            "A service that extracts data from a Modbus Server "
            "and sends it to a local thin-edge.io broker."
        )
        self.logger.info(
            "Documentation: Please refer to the c8y-documentation wiki to find service description"
        )

    def polldata(self):
        for device in self.devices:
            mapper = ModbusMapper(device)
            poll_model = self.build_query_model(device)
            self.polldevice(device, poll_model, mapper)

    def split_set(self, s):
        partitions = []
        v = list(s)
        v.sort()
        cur = []
        i = 0
        while i < len(v):
            cur.append(v[i])
            if i == len(v) - 1 or v[i + 1] > v[i] + 1:
                partitions.append(cur)
                cur = []
            i = i + 1
        return partitions

    def build_query_model(self, device):
        holding_registers = set()
        input_register = set()
        coils = set()
        discret_input = set()
        if device.get("registers") is not None:
            for registerDefiniton in device["registers"]:
                registernumber = registerDefiniton["number"]
                numregisters = int(
                    (registerDefiniton["startbit"] + registerDefiniton["nobits"] - 1)
                    / 16
                )
                registerend = registernumber + numregisters
                registers = list(range(registernumber, registerend + 1))
                if registerDefiniton.get("input") is True:
                    input_register.update(registers)
                else:
                    holding_registers.update(registers)
        if device.get("coils") is not None:
            for coildefinition in device["coils"]:
                coilnumber = coildefinition["number"]
                if coildefinition.get("input") is True:
                    discret_input.add(coilnumber)
                else:
                    coils.add(coilnumber)

        return (
            self.split_set(holding_registers),
            self.split_set(input_register),
            self.split_set(coils),
            self.split_set(discret_input),
        )

    def read_register(self, buf, address=0, count=1):
        return [buf[i] for i in range(address, address + count)]

    def polldevice(self, device, pollmodel, mapper):
        self.logger.debug("Polling device %s", device["name"])
        (
            coil_results,
            di_result,
            hr_results,
            ir_result,
            error,
        ) = self.get_data_from_device(device, pollmodel)
        if error is None:
            # handle all Registers
            if device.get("registers") is not None:
                for registerDefiniton in device["registers"]:
                    try:
                        registernumber = registerDefiniton["number"]
                        numregisters = (
                            int(
                                (
                                    registerDefiniton["startbit"]
                                    + registerDefiniton["nobits"]
                                    - 1
                                )
                                / 16
                            )
                            + 1
                        )
                        if registerDefiniton.get("input"):
                            result = self.read_register(
                                ir_result, address=registernumber, count=numregisters
                            )
                        else:
                            result = self.read_register(
                                hr_results, address=registernumber, count=numregisters
                            )
                        msgs = mapper.mapregister(result, registerDefiniton)
                        for msg in msgs:
                            self.send_tedge_message(msg)
                    except Exception as e:
                        self.logger.error("Failed to map register: %s", e)

            # all Coils
            if device.get("coils") is not None:
                for coildefinition in device["coils"]:
                    try:
                        coilnumber = coildefinition["number"]
                        if coildefinition.get("input") is True:
                            result = self.read_register(
                                di_result, address=coilnumber, count=1
                            )
                        else:
                            result = self.read_register(
                                coil_results, address=coilnumber, count=1
                            )
                        msgs = mapper.mapcoil(result, coildefinition)
                        for msg in msgs:
                            self.send_tedge_message(msg)
                    except Exception as e:
                        self.logger.error("Failed to map coils: %s", e)
        else:
            self.logger.error("Failed to poll device %s: %s", device["name"], error)

        self.poll_scheduler.enter(
            self.baseconfig["modbus"]["pollinterval"],
            1,
            self.polldevice,
            (device, pollmodel, mapper),
        )

    def get_data_from_device(self, device, pollmodel):
        client = ModbusTcpClient(
            host=device["ip"],
            port=device["port"],
            auto_open=True,
            auto_close=True,
            debug=True,
        )
        holdingregister, inputregisters, coils, discreteinput = pollmodel
        hr_results = {}
        ir_result = {}
        coil_results = {}
        di_result = {}
        error = None
        try:
            for hr_range in holdingregister:
                result = client.read_holding_registers(
                    address=hr_range[0],
                    count=hr_range[-1] - hr_range[0] + 1,
                    slave=device["address"],
                )
                if result.isError():
                    self.logger.error("Failed to read holding register: %s", result)
                    continue
                hr_results.update(dict(zip(hr_range, result.registers)))
            for ir_range in inputregisters:
                result = client.read_input_registers(
                    address=ir_range[0],
                    count=ir_range[-1] - ir_range[0] + 1,
                    slave=device["address"],
                )
                if result.isError():
                    self.logger.error("Failed to read input registers: %s", result)
                    continue
                ir_result.update(dict(zip(ir_range, result.registers)))
            for coil_range in coils:
                result = client.read_coils(
                    address=coil_range[0],
                    count=coil_range[-1] - coil_range[0] + 1,
                    slave=device["address"],
                )
                if result.isError():
                    self.logger.error("Failed to read coils: %s", result)
                    continue
                coil_results.update(dict(zip(coil_range, result.bits)))
            for di_range in discreteinput:
                result = client.read_discrete_inputs(
                    address=di_range[0],
                    count=di_range[-1] - di_range[0] + 1,
                    slave=device["address"],
                )
                if result.isError():
                    self.logger.error("Failed to read discrete input: %s", result)
                    continue
                di_result.update(dict(zip(di_range, result.bits)))
        except ConnectionException as e:
            error = e
            self.logger.error("Failed to connect to device: %s: %s", device["name"], e)
        except Exception as e:
            error = e
            self.logger.error("Failed to read: %s", e)
        client.close()
        return coil_results, di_result, hr_results, ir_result, error

    def readbasedefinition(self, basepath):
        if os.path.exists(basepath):
            with open(basepath, encoding="utf8") as file:
                return tomli.load(file)
        else:
            self.logger.error("Base config file %s not found", basepath)
            return {}

    def readdevicedefinition(self, devicepath):
        if os.path.exists(devicepath):
            with open(devicepath, encoding="utf8") as file:
                return tomli.load(file)
        else:
            self.logger.error("Device config file %s not found", devicepath)
            return {}

    def startpolling(self):
        self.reread_config()
        file_watcher_thread = threading.Thread(
            target=self.watchConfigFiles, args=[self.configdir]
        )
        file_watcher_thread.daemon = True
        file_watcher_thread.start()
        self.poll_scheduler.run()

    def send_tedge_message(
        self, msg: MappedMessage, retain: bool = False, qos: int = 0
    ):
        self.logger.debug("sending message %s to topic %s", msg.data, msg.topic)
        self.tedgeClient.publish(
            topic=msg.topic, payload=msg.data, retain=retain, qos=qos
        )

    def connect_to_thinedge(self):
        while True:
            try:
                broker = self.baseconfig["thinedge"]["mqtthost"]
                port = self.baseconfig["thinedge"]["mqttport"]
                client_id = "modbus-client"
                client = mqtt_client.Client(client_id)
                client.connect(broker, port)
                self.logger.debug("Connected to MQTTT broker at %s:%d", broker, port)
                return client
            except Exception as e:
                self.logger.error("Failed to connect to thin-edge.io: %s", e)
                time.sleep(5)

    def send_smartrest_templates(self):
        self.logger.debug("Send smart rest templates to tedge broker")
        topic = "c8y/s/ut/modbus"
        template = "\n".join(str(template) for template in SMARTREST_TEMPLATES)
        self.send_tedge_message(MappedMessage(template, topic))

    def updateBaseConfigOnDevice(self, baseconfig):
        self.logger.debug("Update base config on device")
        topic = "te/device/main///twin/c8y_ModbusConfiguration"
        transmit_rate = baseconfig["modbus"].get("transmitinterval")
        polling_rate = baseconfig["modbus"].get("pollinterval")
        config = {
            "transmitRate": transmit_rate,
            "pollingRate": polling_rate,
        }
        self.send_tedge_message(
            MappedMessage(json.dumps(config), topic), retain=True, qos=1
        )

    def updateModbusInfoOnChildDevices(self, devices):
        for device in devices:
            self.logger.debug("Update modbus info on child device")
            topic = f"te/device/{device['name']}///twin/c8y_ModbusDevice"
            config = {
                "ipAddress": device["ip"],
                "port": device["port"],
                "address": device["address"],
                "protocol": device["protocol"],
            }
            self.send_tedge_message(
                MappedMessage(json.dumps(config), topic), retain=True, qos=1
            )

    def registerService(self):
        self.logger.debug("Register tedge service on device")
        topic = "te/device/main/service/tedge-modbus-plugin"
        data = {"@type": "service", "name": "tedge-modbus-plugin", "type": "service"}
        self.send_tedge_message(
            MappedMessage(json.dumps(data), topic), retain=True, qos=1
        )

    def registerChildDevices(self, devices):
        for device in devices:
            self.logger.debug("Child device registration for device %s", device["name"])
            topic = f"te/device/{device['name']}//"
            payload = {
                "@type": "child-device",
                "name": device["name"],
                "type": "modbus-device",
            }
            self.send_tedge_message(
                MappedMessage(json.dumps(payload), topic), retain=True, qos=1
            )


def main():
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("-c", "--configdir", required=False)
        parser.add_argument("-l", "--logfile", required=False)
        args = parser.parse_args()
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        if args.configdir is not None:
            configdir = os.path.abspath(args.configdir)
        else:
            configdir = None
        poll = ModbusPoll(configdir or defaultFileDir, args.logfile)
        poll.startpolling()
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as mainerr:
        logging.error("Unexpected error. %s", mainerr, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
