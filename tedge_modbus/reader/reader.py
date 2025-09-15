#!/usr/bin/env python3
"""Modbus reader"""
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
from pymodbus.client import ModbusTcpClient, ModbusSerialClient
from pymodbus.exceptions import ConnectionException
from watchdog.events import FileSystemEventHandler, DirModifiedEvent, FileModifiedEvent
from watchdog.observers import Observer

from .banner import BANNER
from .mapper import MappedMessage, ModbusMapper

DEFAULT_FILE_DIR = "/etc/tedge/plugins/modbus"
BASE_CONFIG_NAME = "modbus.toml"
DEVICES_CONFIG_NAME = "devices.toml"


class ModbusPoll:
    """Modbus Poller"""

    class ConfigFileChangedHandler(FileSystemEventHandler):
        """Configuration file changed handler"""

        poller = None

        def __init__(self, poller):
            self.poller = poller

        def on_modified(self, event):
            """handler called when a file is modified"""
            if isinstance(event, DirModifiedEvent):
                return
            if isinstance(event, FileModifiedEvent) and event.event_type == "modified":
                filename = os.path.basename(event.src_path)
                if filename in [BASE_CONFIG_NAME, DEVICES_CONFIG_NAME]:
                    self.poller.reread_config()

    logger: logging.Logger
    tedge_client: mqtt_client.Client = None
    poll_scheduler = sched.scheduler(time.time, time.sleep)
    base_config = {}
    devices = []
    config_dir = "."

    def __init__(self, config_dir=".", logfile=None):
        self.config_dir = config_dir
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
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
        """Reread the configuration"""
        self.logger.info("file change detected, reading files")
        new_base_config = self.read_base_definition(
            f"{self.config_dir}/{BASE_CONFIG_NAME}"
        )
        restart_required = False
        if len(new_base_config) > 1 and new_base_config != self.base_config:
            restart_required = True
            self.base_config = new_base_config
        loglevel = self.base_config["modbus"]["loglevel"] or "INFO"
        self.logger.setLevel(getattr(logging, loglevel.upper(), logging.INFO))
        new_devices = self.read_device_definition(
            f"{self.config_dir}/{DEVICES_CONFIG_NAME}"
        )
        # Add Serial Config into Device Config
        for device in new_devices["device"]:
            if device["protocol"] == "RTU":
                for key in self.base_config["serial"]:
                    if device.get(key, None) is None:
                        device[key] = self.base_config["serial"][key]
        if (
            len(new_devices) >= 1
            and new_devices.get("device")
            and new_devices.get("device") is not None
            and new_devices.get("device") != self.devices
        ):
            restart_required = True
            self.devices = new_devices["device"]
        if restart_required:
            self.logger.info("config change detected, restart polling")
            if self.tedge_client is not None and self.tedge_client.is_connected():
                self.tedge_client.disconnect()
            self.tedge_client = self.connect_to_tedge()
            # If connected to tedge, register service, update config
            time.sleep(5)
            self.register_child_devices(self.devices)
            self.register_service()
            self.update_base_config_on_device(self.base_config)
            self.update_modbus_info_on_child_devices(self.devices)
            for evt in self.poll_scheduler.queue:
                self.poll_scheduler.cancel(evt)
            self.poll_data()

    def watch_config_files(self, config_dir):
        """Start watching configuration files for changes"""
        event_handler = self.ConfigFileChangedHandler(self)
        observer = Observer()
        observer.schedule(event_handler, config_dir)
        observer.start()
        try:
            while True:
                time.sleep(5)
        except Exception as err:
            observer.stop()
            self.logger.error("File observer failed, %s", err, exc_info=True)

    def print_banner(self):
        """Print the application banner"""
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

    def poll_data(self):
        """Poll Modbus data"""
        for device in self.devices:
            mapper = ModbusMapper(device)
            poll_model = self._build_query_model(device)
            self.poll_device(device, poll_model, mapper)

    def _split_set(self, s):
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

    def _build_query_model(self, device):
        holding_registers = set()
        input_register = set()
        coils = set()
        discrete_input = set()
        if device.get("registers") is not None:
            for register_definition in device["registers"]:
                register_number = register_definition["number"]
                num_registers = int(
                    (
                        register_definition["startbit"]
                        + register_definition["nobits"]
                        - 1
                    )
                    / 16
                )
                register_end = register_number + num_registers
                registers = list(range(register_number, register_end + 1))
                if register_definition.get("input") is True:
                    input_register.update(registers)
                else:
                    holding_registers.update(registers)
        if device.get("coils") is not None:
            for coil_definition in device["coils"]:
                coil_number = coil_definition["number"]
                if coil_definition.get("input") is True:
                    discrete_input.add(coil_number)
                else:
                    coils.add(coil_number)

        return (
            self._split_set(holding_registers),
            self._split_set(input_register),
            self._split_set(coils),
            self._split_set(discrete_input),
        )

    def read_register(self, buf, address=0, count=1):
        """Read Modbus register"""
        return [buf[i] for i in range(address, address + count)]

    def poll_device(self, device, poll_model, mapper):
        """Poll a Modbus device"""
        # TODO: Can this be simplified / split to smaller portions?
        # pylint: disable=too-many-branches,too-many-locals
        self.logger.debug("Polling device %s", device["name"])
        (
            coil_results,
            di_result,
            hr_results,
            ir_result,
            error,
        ) = self.get_data_from_device(device, poll_model)
        if error is None:
            # handle all Registers
            if device.get("registers") is not None:
                for register_definition in device["registers"]:
                    try:
                        register_number = register_definition["number"]
                        num_registers = (
                            int(
                                (
                                    register_definition["startbit"]
                                    + register_definition["nobits"]
                                    - 1
                                )
                                / 16
                            )
                            + 1
                        )
                        if register_definition.get("input"):
                            result = self.read_register(
                                ir_result, address=register_number, count=num_registers
                            )
                        else:
                            result = self.read_register(
                                hr_results, address=register_number, count=num_registers
                            )
                        msgs = mapper.map_register(result, register_definition)
                        for msg in msgs:
                            self.send_tedge_message(msg)
                    except Exception as e:
                        self.logger.error("Failed to map register: %s", e)

            # all Coils
            if device.get("coils") is not None:
                for coil_def in device["coils"]:
                    try:
                        coil_number = coil_def["number"]
                        if coil_def.get("input") is True:
                            result = self.read_register(
                                di_result, address=coil_number, count=1
                            )
                        else:
                            result = self.read_register(
                                coil_results, address=coil_number, count=1
                            )
                        msgs = mapper.map_coil(result, coil_def)
                        for msg in msgs:
                            self.send_tedge_message(msg)
                    except Exception as e:
                        self.logger.error("Failed to map coils: %s", e)
        else:
            self.logger.error("Failed to poll device %s: %s", device["name"], error)

        interval = device.get(
            "pollinterval", self.base_config["modbus"]["pollinterval"]
        )
        self.poll_scheduler.enter(
            interval,
            1,
            self.poll_device,
            (device, poll_model, mapper),
        )

    def get_modbus_client(self, device):
        """Get Modbus client"""
        if device["protocol"] == "RTU":
            return ModbusSerialClient(
                port=device["port"],
                baudrate=device["baudrate"],
                stopbits=device["stopbits"],
                parity=device["parity"],
                bytesize=device["databits"],
            )
        if device["protocol"] == "TCP":
            return ModbusTcpClient(
                host=device["ip"],
                port=device["port"],
                # TODO: Check if these parameters really supported by ModbusTcpClient?
                auto_open=True,
                auto_close=True,
                debug=True,
            )
        raise ValueError(
            "Expected protocol to be RTU or TCP. Got " + device["protocol"] + "."
        )

    def get_data_from_device(self, device, poll_model):
        """Get Modbus information from the device"""
        # pylint: disable=too-many-locals
        client = self.get_modbus_client(device)
        holding_register, input_registers, coils, discrete_input = poll_model
        hr_results = {}
        ir_result = {}
        coil_results = {}
        di_result = {}
        error = None
        try:
            for hr_range in holding_register:
                result = client.read_holding_registers(
                    address=hr_range[0],
                    count=hr_range[-1] - hr_range[0] + 1,
                    slave=device["address"],
                )
                if result.isError():
                    self.logger.error("Failed to read holding register: %s", result)
                    continue
                hr_results.update(dict(zip(hr_range, result.registers)))
            for ir_range in input_registers:
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
            for di_range in discrete_input:
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

    def read_base_definition(self, base_path):
        """Read base definition file"""
        if os.path.exists(base_path):
            with open(base_path, mode="rb") as file:
                return tomli.load(file)
        else:
            self.logger.error("Base config file %s not found", base_path)
            return {}

    def read_device_definition(self, device_path):
        """Read device definition file"""
        if os.path.exists(device_path):
            with open(device_path, mode="rb") as file:
                return tomli.load(file)
        else:
            self.logger.error("Device config file %s not found", device_path)
            return {}

    def start_polling(self):
        """Start watching the configuration files and start polling the Modbus server"""
        self.reread_config()
        file_watcher_thread = threading.Thread(
            target=self.watch_config_files, args=[self.config_dir]
        )
        file_watcher_thread.daemon = True
        file_watcher_thread.start()
        self.poll_scheduler.run()

    def send_tedge_message(
        self, msg: MappedMessage, retain: bool = False, qos: int = 0
    ):
        """Send a thin-edge.io message via MQTT"""
        self.logger.debug("sending message %s to topic %s", msg.data, msg.topic)
        self.tedge_client.publish(
            topic=msg.topic, payload=msg.data, retain=retain, qos=qos
        )

    def connect_to_tedge(self):
        """Connect to the thin-edge.io MQTT broker and return a connected MQTT client"""
        while True:
            try:
                broker = self.base_config["thinedge"]["mqtthost"]
                port = self.base_config["thinedge"]["mqttport"]
                client_id = "modbus-client"
                client = mqtt_client.Client(client_id)
                client.connect(broker, port)
                self.logger.debug("Connected to MQTT broker at %s:%d", broker, port)
                return client
            except Exception as e:
                self.logger.error("Failed to connect to thin-edge.io: %s", e)
                time.sleep(5)

    def update_base_config_on_device(self, base_config):
        """Update the base configuration"""
        self.logger.debug("Update base config on device")
        topic = "te/device/main///twin/c8y_ModbusConfiguration"
        transmit_rate = base_config["modbus"].get("transmitinterval")
        polling_rate = base_config["modbus"].get("pollinterval")
        config = {
            "transmitRate": transmit_rate,
            "pollingRate": polling_rate,
        }
        self.send_tedge_message(
            MappedMessage(json.dumps(config), topic), retain=True, qos=1
        )
        if base_config.get("serial") is None:
            return
        topic = "te/device/main///twin/c8y_SerialConfiguration"
        baud_rate = base_config["serial"].get("baudrate")
        stop_bits = base_config["serial"].get("stopbits")
        parity = base_config["serial"].get("parity")
        data_bits = base_config["serial"].get("databits")
        config = {
            "baudRate": baud_rate,
            "stopBits": stop_bits,
            "parity": parity,
            "dataBits": data_bits,
        }
        self.send_tedge_message(
            MappedMessage(json.dumps(config), topic), retain=True, qos=1
        )

    def update_modbus_info_on_child_devices(self, devices):
        """Update the modbus information for the child devices"""
        for device in devices:
            self.logger.debug("Update modbus info on child device")
            topic = f"te/device/{device['name']}///twin/c8y_ModbusDevice"
            config = {
                "port": device["port"],
                "address": device["address"],
                "protocol": device["protocol"],
            }
            if device["protocol"] == "TCP":
                config["ipAddress"] = device["ip"]
            self.send_tedge_message(
                MappedMessage(json.dumps(config), topic), retain=True, qos=1
            )

    def register_service(self):
        """Register the service with thin-edge.io"""
        self.logger.debug("Register tedge service on device")
        topic = "te/device/main/service/tedge-modbus-plugin"
        data = {"@type": "service", "name": "tedge-modbus-plugin", "type": "service"}
        self.send_tedge_message(
            MappedMessage(json.dumps(data), topic), retain=True, qos=1
        )

    def register_child_devices(self, devices):
        """Register the child devices with thin-edge.io"""
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
    """Main"""
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("-c", "--configdir", required=False)
        parser.add_argument("-l", "--logfile", required=False)
        args = parser.parse_args()
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        if args.configdir is not None:
            config_dir = os.path.abspath(args.configdir)
        else:
            config_dir = None
        poll = ModbusPoll(config_dir or DEFAULT_FILE_DIR, args.logfile)
        poll.start_polling()
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as main_err:
        logging.error("Unexpected error. %s", main_err, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
