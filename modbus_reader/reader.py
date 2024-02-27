#!/usr/bin/python3
# coding=utf-8
import argparse
import json
import logging
import os.path
import sched
import sys
import threading
import time

import pyfiglet
import tomli
from paho.mqtt import client as mqtt_client
from pymodbus.client.tcp import ModbusTcpClient
from pymodbus.exceptions import ConnectionException
from watchdog.events import FileSystemEventHandler, DirModifiedEvent, FileModifiedEvent
from watchdog.observers import Observer

from mapper import MappedMessage, ModbusMapper
from smartresttemplates import SMARTREST_TEMPLATES

defaultFileDir = "/etc/tedge/plugins/modbus"
baseConfigName = 'modbus.toml'
devicesConfigName = 'devices.toml'


class ModbusPoll:
    class ConfigFileChangedHandler(FileSystemEventHandler):
        poller = None

        def __init__(self, poller):
            self.poller = poller

        def on_modified(self, event):
            if isinstance(event, DirModifiedEvent):
                return
            elif isinstance(event, FileModifiedEvent) and event.event_type == 'modified':
                filename = os.path.basename(event.src_path)
                if filename == baseConfigName or filename == devicesConfigName:
                    self.poller.reread_config()

    logger: logging.Logger
    tedgeClient: mqtt_client.Client = None
    poll_scheduler = sched.scheduler(time.time, time.sleep)
    baseconfig = {}
    devices = []
    configdir = '.'

    def __init__(self, configdir='.', logfile=None):
        self.configdir = configdir
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        if logfile is not None:
            fh = logging.FileHandler(logfile)
            fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            self.logger.addHandler(fh)
        self.print_banner()

    def reread_config(self):
        self.logger.info('file change detected, reading files')
        newbaseconfig = self.readbasedefinition(f'{self.configdir}/{baseConfigName}')
        restartrequired = False
        if len(newbaseconfig) > 1 and newbaseconfig != self.baseconfig:
            restartrequired = True
            self.baseconfig = newbaseconfig
        newdevices = self.readdevicedefinition(f'{self.configdir}/{devicesConfigName}')
        if len(newdevices) >= 1 and newdevices.get('device') and newdevices.get(
                'device') is not None and newdevices.get('device') != self.devices:
            restartrequired = True
            self.devices = newdevices['device']
        if restartrequired:
            self.logger.info('config change detected, restart polling')
            if self.tedgeClient is not None and self.tedgeClient.is_connected():
                self.tedgeClient.disconnect()
            self.tedgeClient = self.connect_to_thinedge()
            #If connected to tedge, register service, update config and send smart rest template
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
            self.logger.error('File observer failed')

    def print_banner(self):
        self.logger.info(pyfiglet.figlet_format("Modbus plugin for thin-edge.io"))
        self.logger.info("Author:\t\tRina,Mario,Murat")
        self.logger.info("Date:\t\t12th October 2022")
        self.logger.info(
            "Description:\tA service that extracts data from a Modbus Server and sends it to a local thin-edge.io broker.")
        self.logger.info("Documentation:\tPlease refer to the c8y-documentation wiki to find service description")

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
        if device.get('registers') is not None:
            for registerDefiniton in device['registers']:
                registernumber = registerDefiniton['number']
                numregisters = int((registerDefiniton['startbit'] + registerDefiniton['nobits'] - 1) / 16)
                registerend = registernumber + numregisters
                registers = [x for x in range(registernumber, registerend + 1)]
                if registerDefiniton.get('input') == True:
                    input_register.update(registers)
                else:
                    holding_registers.update(registers)
        if device.get('coils') is not None:
            for coildefinition in device['coils']:
                coilnumber = coildefinition['number']
                if coildefinition.get('input') == True:
                    discret_input.add(coilnumber)
                else:
                    coils.add(coilnumber)

        return (self.split_set(holding_registers), self.split_set(input_register), self.split_set(coils),
                self.split_set(discret_input))

    def read_register(self, buf, address=0, count=1):
        return [buf[i] for i in range(address, address + count)]

    def polldevice(self, device, pollmodel, mapper):
        self.logger.debug(f'Polling device {device["name"]}')
        coil_results, di_result, hr_results, ir_result, error = self.get_data_from_device(device, pollmodel)
        if error is None:

            # handle all Registers
            if device.get('registers') is not None:
                for registerDefiniton in device['registers']:
                    try:
                        registernumber = registerDefiniton['number']
                        numregisters = int((registerDefiniton['startbit'] + registerDefiniton['nobits'] - 1) / 16) + 1
                        if registerDefiniton.get('input') == True:
                            result = self.read_register(ir_result, address=registernumber, count=numregisters)
                        else:
                            result = self.read_register(hr_results, address=registernumber, count=numregisters)
                        msgs = mapper.mapregister(result, registerDefiniton)
                        for msg in msgs:
                            self.send_tedge_message(msg)
                    except Exception as e:
                        self.logger.error(f'Failed to map register: {e}')

            # all Coils
            if device.get('coils') is not None:
                for coildefinition in device['coils']:
                    try:
                        coilnumber = coildefinition['number']
                        if coildefinition.get('input') == True:
                            result = self.read_register(di_result, address=coilnumber, count=1)
                        else:
                            result = self.read_register(coil_results, address=coilnumber, count=1)
                        msgs = mapper.mapcoil(result, coildefinition)
                        for msg in msgs:
                            self.send_tedge_message(msg)
                    except Exception as e:
                        self.logger.error(f'Failed to map coils: {e}')
        else:
            self.logger.error(f'Failed to poll device {device["name"]}: {error}')

        self.poll_scheduler.enter(self.baseconfig['modbus']['pollinterval'], 1, self.polldevice,
                                  (device, pollmodel, mapper))

    def get_data_from_device(self, device, pollmodel):
        client = ModbusTcpClient(host=device['ip'], port=device['port'], auto_open=True, auto_close=True, debug=True)
        holdingregister, inputregisters, coils, discreteinput = pollmodel
        hr_results = {}
        ir_result = {}
        coil_results = {}
        di_result = {}
        error = None
        try:
            for hr_range in holdingregister:
                result = client.read_holding_registers(address=hr_range[0], count=hr_range[-1] - hr_range[0] + 1,
                                                       slave=device['address'])
                if result.isError():
                    self.logger.error(f'Failed to read holding register: {result}')
                    continue
                hr_results.update(dict(zip(hr_range, result.registers)))
            for ir_range in inputregisters:
                result = client.read_input_registers(address=ir_range[0], count=ir_range[-1] - ir_range[0] + 1,
                                                     slave=device['address'])
                if result.isError():
                    self.logger.error(f'Failed to read input registers: {result}')
                    continue
                ir_result.update(dict(zip(ir_range, result.registers)))
            for coil_range in coils:
                result = client.read_coils(address=coil_range[0], count=coil_range[-1] - coil_range[0] + 1,
                                           slave=device['address'])
                if result.isError():
                    self.logger.error(f'Failed to read coils: {result}')
                    continue
                coil_results.update(dict(zip(coil_range, result.bits)))
            for di_range in discreteinput:
                result = client.read_discrete_inputs(address=di_range[0], count=di_range[-1] - di_range[0] + 1,
                                                     slave=device['address'])
                if result.isError():
                    self.logger.error(f'Failed to read discrete input: {result}')
                    continue
                di_result.update(dict(zip(di_range, result.bits)))
        except ConnectionException as e:
            error = e
            self.logger.error(f'Failed to connect to device: {device["name"]}: {e}')
        except Exception as e:
            error = e
            self.logger.error(f'Failed to read: {e}')
        client.close()
        return coil_results, di_result, hr_results, ir_result, error

    def readbasedefinition(self, basepath):
        if os.path.exists(basepath):
            with open(basepath) as fileObj:
                return tomli.loads(fileObj.read())
        else:
            self.logger.error(f'Base config file {basepath} not found')
            return {}
 

    def readdevicedefinition(self, devicepath):
        if os.path.exists(devicepath):
            with open(devicepath) as deviceObj:
                return tomli.loads(deviceObj.read())
        else:
            self.logger.error(f'Device config file {devicepath} not found')
            return {}

    def startpolling(self):
        self.reread_config()
        file_watcher_thread = threading.Thread(target=self.watchConfigFiles, args=[self.configdir])
        file_watcher_thread.daemon = True
        file_watcher_thread.start()
        self.poll_scheduler.run()

    def send_tedge_message(self, msg: MappedMessage):
        self.logger.debug(f'sending message {msg.data} to topic {msg.topic}')
        self.tedgeClient.publish(topic=msg.topic, payload=msg.data)

    def connect_to_thinedge(self):
        while True:
            try:
                broker = self.baseconfig['thinedge']['mqtthost']
                port = self.baseconfig['thinedge']['mqttport']
                client_id = f'modbus-client'
                client = mqtt_client.Client(client_id)
                client.connect(broker, port)
                self.logger.debug(f'Connected to MQTTT broker at {broker}:{port}')
                return client
            except Exception as e:
                self.logger.error(f'Failed to connect to thin-edge: {e}')
                time.sleep(5)

    def send_smartrest_templates(self):
        self.logger.debug(f'Send smart rest templates to tedge broker')
        topic = "c8y/s/ut/modbus"
        template = '\n'.join(str(template) for template in SMARTREST_TEMPLATES)
        
        self.send_tedge_message(MappedMessage(template,topic))

    def updateBaseConfigOnDevice(self, baseconfig):
        self.logger.debug(f'Update base config on device')
        topic = "te/device/main///twin/c8y_ModbusConfiguration"        
        transmit_rate = baseconfig['modbus'].get('pollrate')
        polling_rate = baseconfig['modbus'].get('pollinterval')        
        config = {
            "transmitRate": transmit_rate if transmit_rate is not None else None,
            "pollingRate": polling_rate if polling_rate is not None else None,
        }
        self.send_tedge_message(MappedMessage(json.dumps(config),topic))

    def updateModbusInfoOnChildDevices(self, devices):
        for device in devices:
            self.logger.debug(f'Update modbus info on child device')
            topic = f"te/device/{device['name']}///twin/c8y_ModbusDevice"
            config = {
                "ipAddress": device['ip'],
                "protocol": device['port'],
                "address": device['address'],
                "protocol": device['protocol'],
            }
            self.send_tedge_message(MappedMessage(json.dumps(config),topic))

    
    def registerService(self):
        self.logger.debug(f'Register tedge service on device')
        topic = "te/device/main/service/tedge-modbus-plugin"
        data = {"@type":"service","name":"tedge-modbus-plugin","type":"service"}
        self.send_tedge_message(MappedMessage(json.dumps(data),topic))

    def registerChildDevices(self, devices):
        for device in devices:
            self.logger.debug(f'Child device registration for device {device["name"]}')
            topic = f"te/device/{device['name']}//"
            payload = {
                    "@type": "child-device",
                    "name": device['name'],
                    "type": "modbus-device"
            }
            self.send_tedge_message(MappedMessage(json.dumps(payload),topic))
            
def main():
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument('-c', '--configdir', required=False)
        parser.add_argument('-l', '--logfile', required=False)
        args = parser.parse_args()
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        if args.configdir is not None:
            configdir = os.path.abspath(args.configdir)
        else:
            configdir = None
        poll = ModbusPoll(configdir or defaultFileDir, args.logfile)
        poll.startpolling()
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as mainerr:
        print(f'The following error occured: {mainerr}')


if __name__ == "__main__":
    main()
