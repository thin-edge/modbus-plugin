#!/usr/bin/python3
# coding=utf-8
import logging
import sys
from paho.mqtt import client as mqtt_client
import requests
import toml

logger = logging.getLogger("c8y_ModbusConfiguration")
logFile = f'/var/log/tedge/c8y_ModbusConfiguration.log'
logging.basicConfig(filename=logFile,level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logger.info(f'New c8y_ModbusConfiguration operation')


#TODO: Get broker and port from thin-edge options
broker = 'localhost'
port = 1883
client_id = "c8y_ModbusConfiguration-operation-client"

# fileDir = "/etc/tedge"
# fileName = f'{__name__}.toml'

# configFile = f'{fileDir}/{fileName}'
#Connect to local thin edge broker
logger.debug(f'Connecting to local thin-edge broker at {broker}:{port}')
client = mqtt_client.Client(client_id)
client.connect(broker, port)
logger.info(f'Mtqq client with id {client_id} connected to local thin-edge broker at {broker}:{port}')
try:
    #Set operation status to executing
    client.publish('c8y/s/us',f'501,{"c8y_ModbusConfiguration"}')

    #Check and store arguments
    arguments = sys.argv[1].split(',')
    if len(arguments) != 8:
        raise ValueError("Expected 8 arguments in smart rest template. Got " + str(len(arguments)) + ".")
    modbusType = arguments[2]
    modbusAddress = arguments[3]
    childName = arguments[4]
    modbusServer = arguments[5]
    #deviceId = array[6]
    mappingPath = arguments[7]

    #Get the mapping json via rest
    url = f'http://{broker}:8001/c8y{mappingPath}'
    logger.debug(f'Getting mapping json from {url}')
    response = requests.get(url)
    logger.info(f'Got mapping json from {url} with response {response.status_code}')
    if response.status_code != 200:
        raise Exception(f'Error getting mapping at {mappingPath}. Got response {response.status_code} from {url}. Expected 200.')
    mappingJson = response.json()
    # logger.debug(f'Got mapping json: {mappingJson}')
    #Create the mapping toml
    #Device data
    mappingToml = {}
    mappingToml["device"] = [{}]
    mappingToml["device"][0]["address"]=modbusAddress
    mappingToml["device"][0]["name"]=childName
    mappingToml["device"][0]["address"]=modbusAddress
    mappingToml["device"][0]["ip"]=modbusServer
    mappingToml["device"][0]["port"]=502
    mappingToml["device"][0]["protocol"]="TCP" #Only support for TCP
    mappingToml["device"][0]["littlewordendian"]=True

    #Registers
    mappingToml["device"][0]["registers"] = [{}]*len(mappingJson["c8y_Registers"])
    for i,c8yRegister in enumerate(mappingJson["c8y_Registers"]):

        mappingToml["device"][0]["registers"][i]["number"]=c8yRegister["number"]
        mappingToml["device"][0]["registers"][i]["startbit"]=c8yRegister["startBit"]
        mappingToml["device"][0]["registers"][i]["nobits"]=c8yRegister["noBits"]
        mappingToml["device"][0]["registers"][i]["signed"]=c8yRegister["signed"]
        mappingToml["device"][0]["registers"][i]["multiplier"]=c8yRegister["multiplier"]
        mappingToml["device"][0]["registers"][i]["divisor"]=c8yRegister["divisor"]
        mappingToml["device"][0]["registers"][i]["decimalshiftright"]=c8yRegister["offset"]

        #Measurements
        if "measurementMapping" in c8yRegister:
             mappingToml["device"][0]["registers"][i]["measurementmapping.templatestring"]=f'{{\\"{c8yRegister["measurementMapping"]["type"]}\\":{{\\"{c8yRegister["measurementMapping"]["series"]}\\":%%}} }}'

    logger.debug(f'Created mapping toml: {mappingToml}')
    #Store the mapping toml:
    pathToConfig = "/etc/tedge/plugins/modbus/device.toml" 
    logger.debug(f'Storing mapping toml at {pathToConfig}')

    tomlString = toml.dumps(mappingToml)
    with open(pathToConfig, "w") as tomlFile:
        tomlFile.write(tomlString)
    logger.info(f'Stored mapping toml at {pathToConfig}')

    #Set operation status to success
    client.publish('c8y/s/us',f'503,{"c8y_ModbusConfiguration"},')



except Exception as e:
    client.publish('c8y/s/us',f'502,{"c8y_ModbusConfiguration"},"Error: {e}"')
    logger.error(f'Error: {e}')
