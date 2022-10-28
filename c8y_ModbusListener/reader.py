#!/usr/bin/python3
# coding=utf-8
import logging
import time
import argparse
import pyfiglet
import sys
import tomli
import sched
from pymodbus.client import ModbusTcpClient
from paho.mqtt import client as mqtt_client

from c8y_ModbusListener.mapper import ModbusMapper
from c8y_ModbusListener.mapper import MappedMessage

topics = {
    'measurement': 'tedge/measurements/CHILD_ID',
    'event': 'tedge/events/EVENT_ID/CHILD_ID',
    'alarm': 'tedge/alarms/SEVERITY/TYPE/CHILD_ID'
}
defaultFileDir = "/etc/tedge/plugins/modbus"
baseConfigName = 'modbus.toml'
devicesConfigName = 'devices.toml'


class ModbusPoll:
    logger: logging.Logger
    tedgeClient = None
    mapper = None
    baseconfig = {}
    devices = []

    def __init__(self, configDir='.'):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.print_banner()
        self.readbasedefinition(f'{configDir}/{baseConfigName}')
        self.readdevicedefinition(f'{configDir}/{devicesConfigName}')
        self.mapper = ModbusMapper({})
        self.tedgeClient = self.connect_to_thinedge()

    def print_banner(self):
        self.logger.info(pyfiglet.figlet_format("Modbus plugin for thin-edge.io"))
        self.logger.info("Author:\t\tRina,Mario,Murat")
        self.logger.info("Date:\t\t12th October 2022")
        self.logger.info(
            "Description:\tA service that extracts data from a Modbus Server and sends it to a local thin-edge.io broker.")
        self.logger.info("Documentation:\tPlease refer to the c8y-documentation wiki to find service description")

    def polldata(self):
        scheduler = sched.scheduler(time.time, time.sleep)
        for device in self.devices['device']:
            scheduler.enter(self.baseconfig['modbus']['pollinterval'], 1, self.polldevice, (device, scheduler,))
            scheduler.run()

    def polldevice(self, device, scheduler):
        self.logger.debug(f'Polling device {device["name"]}')
        client = ModbusTcpClient(host=device['ip'], port=device['port'], auto_open=True, auto_close=True, debug=True)
        if not device.get('registers') is None:
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
                    msg = self.mapper.maphrregister(result, registerDefiniton)
                    self.logger.debug(f'sending message {msg.data}')
                    self.send_tedge_message(device, msg)
                except Exception as e:
                    self.logger.error(f'Failed to read and map register: {e}')
        if not device.get('coils') is None:
            for coil in device['coils']:
                self.logger.debug(coil)
        client.close()
        scheduler.enter(self.baseconfig['modbus']['pollinterval'], 1, self.polldevice, (device, scheduler,))

    def readbasedefinition(self, basepath):
        with open(basepath) as fileObj:
            self.baseconfig = tomli.loads(fileObj.read())

    def readdevicedefinition(self, devicepath):
        with open(devicepath) as deviceObj:
            self.devices = tomli.loads(deviceObj.read())

    def startpolling(self):
        self.polldata()

    def send_tedge_message(self, device, msg: MappedMessage):
        topic = topics[msg.type].replace('CHILD_ID', device.get('name'))
        self.tedgeClient.publish(topic=topic, payload=msg.data)

    def connect_to_thinedge(self):
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


if __name__ == "__main__":
    try:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        parser = argparse.ArgumentParser()
        parser.add_argument('-c', '--configdir', required=False)
        args = parser.parse_args()
        poll = ModbusPoll(args.configdir or defaultFileDir)
        poll.startpolling()
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as mainerr:
        print(f'The following error occured: {mainerr}')
