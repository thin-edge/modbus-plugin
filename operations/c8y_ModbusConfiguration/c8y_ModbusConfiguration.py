#!/etc/tedge/plugins/modbus/venv/bin/python3 
# coding=utf-8
import logging
import sys
from paho.mqtt import client as mqtt_client
import json
import toml

logger = logging.getLogger("c8y_ModbusConfiguration")
logFile = f'/var/log/tedge/c8y_ModbusConfiguration.log'
logging.basicConfig(filename=logFile,level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logger.info(f'New c8y_ModbusConfiguration operation')


#TODO: Get broker and port from thin-edge options
broker = 'localhost'
port = 1883
client_id = "c8y_ModbusConfiguration-operation-client"
config_path = "/etc/tedge/plugins/modbus/modbus.toml"


#Connect to local thin edge broker
logger.debug(f'Connecting to local thin-edge broker at {broker}:{port}')
client = mqtt_client.Client(client_id)
client.connect(broker, port)
logger.info(f'MQTT client with id {client_id} connected to local thin-edge broker at {broker}:{port}')
try:
    arguments = sys.argv[1].split(',')
    if len(arguments) != 4:
        raise ValueError("Expected 4 arguments in smart rest template. Got " + str(len(arguments)) + ".")
    logger.debug(f'Arguments: {arguments}')
    transmit_rate = int(arguments[2])
    polling_rate = int(arguments[3])
    logger.debug(f'transmitRate: {transmit_rate} pollingRate: {polling_rate}')

    #Get device configuration
    logger.info(f'Read mapping toml from {config_path}')
    modbus_config = toml.load(config_path)    
    logger.debug(f'Current configuration: {modbus_config}')

    #Update configuration
    modbus_config['modbus']['transmitinterval'] = transmit_rate
    modbus_config['modbus']['pollinterval'] = polling_rate

    #Save to file
    logger.info(f'Saving new configuration to {config_path}')
    with open(config_path, 'w') as f:
        toml.dump(modbus_config, f)
    logger.info(f'New configuration saved to {config_path}')


    #Update managedObject
    logger.debug(f'Updating managedObject with new configuration')
    topic = "te/device/main///twin/c8y_ModbusConfiguration"    
      
    config = {
            "transmitRate": transmit_rate if transmit_rate is not None else None,
            "pollingRate": polling_rate if polling_rate is not None else None,
    }
    client.publish(topic, json.dumps(config))


    #Set operation status to success
    client.publish('c8y/s/us',"503,c8y_ModbusConfiguration")



except Exception as e:
    client.publish('c8y/s/us',f'502,c8y_ModbusConfiguration,"Error: {e}"')
    logger.error(f'Error: {e}')
