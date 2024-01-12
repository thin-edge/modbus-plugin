#!/etc/tedge/plugins/modbus/venv/bin/python3 
# coding=utf-8
import logging
import subprocess
import sys
from paho.mqtt import client as mqtt_client
import requests
import toml

def get_tedge_id():
    try:
        # Run the command and capture the output
        result = subprocess.run(['tedge', 'config', 'get', 'device.id'], capture_output=True, text=True, check=True)

        # Access the output value
        device_id = result.stdout.strip()

        return device_id
    except subprocess.CalledProcessError as e:
        raise(e)



def update_or_create_device_mapping(mapping, child_name, modbus_address, modbus_server, modbus_type, new_mapping):
    devices = mapping.setdefault('device', [])
    for i, device in enumerate(devices):
        if device.get("name") == child_name:
            devices[i] = get_device_from_mapping(child_name, modbus_address, modbus_server, modbus_type, new_mapping)
            return
    devices.append(get_device_from_mapping(child_name, modbus_address, modbus_server, modbus_type, new_mapping))

def get_device_from_mapping(childName, modbus_address, modbus_server, modbus_type, mapping):
    device = {}
    device["name"] = childName
    device["address"] = int(modbus_address)
    device["ip"] = modbus_server
    device["port"] = 502
    device["protocol"] = modbus_type
    device["littlewordendian"] = True

    #Registers
    device["registers"] = [{}]*len(mapping["c8y_Registers"])
   
    for i,c8yRegister in enumerate(mapping["c8y_Registers"]):

        device["registers"][i]["number"]=c8yRegister["number"]
        device["registers"][i]["startbit"]=c8yRegister["startBit"]
        device["registers"][i]["nobits"]=c8yRegister["noBits"]
        device["registers"][i]["signed"]=c8yRegister["signed"]
        device["registers"][i]["multiplier"]=c8yRegister["multiplier"]
        device["registers"][i]["divisor"]=c8yRegister["divisor"]
        device["registers"][i]["decimalshiftright"]=c8yRegister["offset"]
        device["registers"][i]["input"]=c8yRegister["input"]
        #Measurements
        if "measurementMapping" in c8yRegister:
            #device["registers"][i]['measurementmapping'] = {}
            measurementmapping = {}
            measurementmapping['templatestring'] = f'{{"{c8yRegister["measurementMapping"]["type"]}":{{"{c8yRegister["measurementMapping"]["series"]}":%%}} }}'
            device["registers"][i]["measurementmapping"] = measurementmapping

    return device

logger = logging.getLogger("c8y_ModbusDevice")
logFile = f'/var/log/tedge/c8y_ModbusDevice.log'
logging.basicConfig(filename=logFile,level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logger.info(f'New c8y_ModbusDevice operation')


#TODO: Get broker and port from thin-edge options
broker = 'localhost'
port = 1883
client_id = "c8y_ModbusDevice-operation-client"

config_path = "/etc/tedge/plugins/modbus/devices.toml" 

# fileDir = "/etc/tedge"
# fileName = f'{__name__}.toml'

# configFile = f'{fileDir}/{fileName}'
#Connect to local thin edge broker
logger.debug(f'Connecting to local thin-edge broker at {broker}:{port}')
client = mqtt_client.Client(client_id)
client.connect(broker, port)
logger.info(f'MQTT client with id {client_id} connected to local thin-edge broker at {broker}:{port}')
try:
    #Check and store arguments
    arguments = sys.argv[1].split(',')
    if len(arguments) != 8:
        raise ValueError("Expected 8 arguments in smart rest template. Got " + str(len(arguments)) + ".")
    modbus_type = arguments[2] #Only works for TCP.
    modbus_address = arguments[3]
    child_name = arguments[4]
    modbus_server = arguments[5]
    deviceId = arguments[6]
    mapping_path = arguments[7]

    #Fail if modbus_type is not TCP
    if modbus_type != "TCP":
        raise ValueError("Expected modbus_type to be TCP. Got " + modbus_type + ".")

    #Update external id of child device
    logger.debug(f'Create external id for child device {deviceId}')
    url = f'http://{broker}:8001/c8y/identity/globalIds/{deviceId}/externalIds'
    tedge_id = get_tedge_id()
    data = {"externalId": f'{tedge_id}:device:{child_name}', "type": "c8y_Serial"}
    response = requests.post(url, json=data)
    if response.status_code != 201:
        raise Exception(f'Error creating external id for child device with id {deviceId}. Got response {response.status_code} from {url}. Expected 201.')
    logger.info(f'Created external id for child device with id {deviceId} to {data["externalId"]}')

    #Get the mapping json via rest
    url = f'http://{broker}:8001/c8y{mapping_path}'
    logger.debug(f'Getting mapping json from {url}')
    response = requests.get(url)
    logger.info(f'Got mapping json from {url} with response {response.status_code}')
    if response.status_code != 200:
        raise Exception(f'Error getting mapping at {mapping_path}. Got response {response.status_code} from {url}. Expected 200.')
    new_mapping = response.json()
    
    #Read the mapping toml from pathToConfig
    logger.debug(f'Reading mapping toml from {config_path}')
    mapping = toml.load(config_path)
    logger.info(f'Read mapping toml from {config_path}')
  

    #Update or create device data for the device with the same childName
    logger.debug(f'Updating or creating device data for device with childName {child_name}')
    update_or_create_device_mapping(mapping, child_name, modbus_address, modbus_server, modbus_type, new_mapping)
    
    logger.debug(f'Created mapping toml: {mapping}')

    #Store the mapping toml:
    logger.debug(f'Storing mapping toml at {config_path}')

    tomlString = toml.dumps(mapping)
    with open(config_path, "w") as tomlFile:
        tomlFile.write(tomlString)
    logger.info(f'Stored mapping toml at {config_path}')

    #Set operation status to success
    client.publish('c8y/s/us',"503,c8y_ModbusDevice")



except Exception as e:
    client.publish('c8y/s/us',f'502,c8y_ModbusDevice,"Error: {e}"')
    logger.error(f'Error: {e}')


