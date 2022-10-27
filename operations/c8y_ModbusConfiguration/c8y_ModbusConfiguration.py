#!/usr/bin/python3
# coding=utf-8
import logging

logger = logging.getLogger(__name__)
logFile = f'/var/log/{__name__}.log'
logging.basicConfig(filename=logFile,level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logger.info(f'Logger for {__name__} was initialised')

import sys
from paho.mqtt import client as mqtt_client
from os import path,makedirs

broker = 'localhost'
port = 1883
client_id = f'{__name__}-operation-client'

fileDir = "/etc/tedge"
fileName = f'{__name__}.toml'

configFile = f'{fileDir}/{fileName}'

array = sys.argv[1].split(',')
client = mqtt_client.Client(client_id)
client.connect(broker, port)


try:
    client.publish('c8y/s/us',f'501,{__name__}')
    if not path.exists(fileDir):
        print("Directory does not exist, creating it.")
        makedirs(fileDir)
    with open(configFile, mode='w', newline='') as file:
        file.write(array)
    client.publish('c8y/s/us',f'503,{__name__},')
except Exception as e:
    client.publish('c8y/s/us',f'502,{__name__},"Error: {e}"')
