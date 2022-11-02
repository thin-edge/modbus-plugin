#!/usr/bin/python3
# coding=utf-8
import argparse
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

from modbus_reader.mapper import MappedMessage, ModbusMapper

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
            self.polldevice(device)
        self.poll_scheduler.enter(self.baseconfig['modbus']['pollinterval'], 1, self.polldata, ())

    def polldevice(self, device):
        self.logger.debug(f'Polling device {device["name"]}')
        client = ModbusTcpClient(host=device['ip'], port=device['port'], auto_open=True, auto_close=True, debug=True)
        mapper = ModbusMapper(device)

        # read and handle all Registers
        if device.get('registers') is not None:
            for registerDefiniton in device['registers']:
                try:
                    registernumber = registerDefiniton['number']
                    numregisters = int((registerDefiniton['startbit'] + registerDefiniton['nobits'] - 1) / 16) + 1
                    if registerDefiniton.get('input') == True:
                        result = client.read_input_registers(address=registernumber, count=numregisters,
                                                             slave=device['address'])
                    else:
                        result = client.read_holding_registers(address=registernumber, count=numregisters,
                                                               slave=device['address'])
                    if result.isError():
                        self.logger.error(f'Failed to read register: {result}')
                        continue
                    msgs = mapper.mapregister(result, registerDefiniton)
                    for msg in msgs:
                        self.send_tedge_message(msg)
                except ConnectionException as e:
                    self.logger.error(f'Failed to connect to device: {device["name"]}')
                    return
                except Exception as e:
                    self.logger.error(f'Failed to read and map register: {e}')

        # read and handle all Coils
        if device.get('coils') is not None:
            for coildefinition in device['coils']:
                try:
                    coilnumber = coildefinition['number']
                    if coildefinition.get('input') == True:
                        result = client.read_coils(address=coilnumber, count=1,
                                                   slave=device['address'])
                    else:
                        result = client.read_discrete_inputs(address=coilnumber, count=1, slave=device['address'])
                    if result.isError():
                        self.logger.error(f'Failed to read coil: {result}')
                        continue
                    msgs = mapper.mapcoil(result, coildefinition)
                    for msg in msgs:
                        self.logger.debug(f'sending message {msg.data}')
                        self.send_tedge_message(msg)
                except ConnectionException as e:
                    self.logger.error(f'Failed to connect to device: {device["name"]}')
                    return
                except Exception as e:
                    self.logger.error(f'Failed to read and map register: {e}')

        client.close()

    def readbasedefinition(self, basepath):
        with open(basepath) as fileObj:
            return tomli.loads(fileObj.read())

    def readdevicedefinition(self, devicepath):
        with open(devicepath) as deviceObj:
            return tomli.loads(deviceObj.read())

    def startpolling(self):
        self.reread_config()
        file_watcher_thread = threading.Thread(target=self.watchConfigFiles, args=[self.configdir])
        file_watcher_thread.daemon = True
        file_watcher_thread.start()
        self.polldata()
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
