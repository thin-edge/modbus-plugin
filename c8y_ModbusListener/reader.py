#!/usr/bin/python3
# coding=utf-8
import logging
import time

import pyfiglet
import sys
import tomli
import sched
from pyModbusTCP.client import ModbusClient
from paho.mqtt import client as mqtt_client

from c8y_ModbusListener.mapper import ModbusMapper


class ModbusPoll:
    logger = logging.getLogger('Logger')
    tedgeClient = None
    mapper = None
    baseconfig = {}
    devices = []

    def __init__(self):
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.print_banner()
        self.readbasedefinition()
        self.readdevicedefinition()
        mapper = ModbusMapper({})
        self.tedgeClient = self.connect_to_thinedge()

    def print_banner(self):
        self.logger.info(pyfiglet.figlet_format("Modbus plugin for thin-edge.io"))
        self.logger.info("Author:\t\tRina,Mario,Murat")
        self.logger.info("Date:\t\t12th October 2022")
        self.logger.info("Description:\tA service that extracts data from a Modbus Server and sends it to a local thin-edge.io broker.")
        self.logger.info("Documentation:\tPlease refer to the c8y-documentation wiki to find service description")

    def polldata(self):
        scheduler = sched.scheduler(time.time, time.sleep)
        for device in self.devices['device']:
            scheduler.enter(15, 1, self.polldevice, (device, scheduler,))
            scheduler.run()

    def polldevice(self, device, scheduler):
        client = ModbusClient(host=device['ip'], port=device['port'], auto_open=True, auto_close=True, debug=True)
        result = client.read_holding_registers(0, 1)
        msg = self.mapper.mapregister(result)
        self.logger.debug(result)
        scheduler.enter(15, 1, self.polldevice, (device, scheduler,))

    def readbasedefinition(self):
        with open('../config/modbus.toml') as fileObj:
            self.baseconfig = tomli.loads(fileObj.read())

    def readdevicedefinition(self):
        with open('../config/devices.toml') as deviceObj:
            self.devices = tomli.loads(deviceObj.read())

    def startpolling(self):
        self.polldata()

    def connect_to_thinedge(self):
        try:
            broker = self.baseconfig['thinedge']['mqtthost']
            port = self.baseconfig['thinedge']['mqttport']
            client_id = f'modbus-client'
            client = mqtt_client.Client(client_id)
            client.connect(broker, port)
            return client
        except Exception as e:
            self.logger.error(f'Failed to connect to thin-edge: {e}')



if __name__== "__main__":
    try:
        poll = ModbusPoll()
        poll.startpolling()
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as e:
        poll.logger.error(f'The following error occured: {e}')