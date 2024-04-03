#!/usr/bin/env python3
import json
import logging
import sys
import toml
from paho.mqtt.publish import single as mqtt_publish

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger.info("New c8y_ModbusConfiguration operation")

# TODO: Get broker and port from thin-edge options
BROKER = "localhost"
PORT = 1883
CLIENT_ID = "c8y_ModbusConfiguration-operation-client"
CONFIG_PATH = "/etc/tedge/plugins/modbus/modbus.toml"

try:
    arguments = sys.argv[1].split(",")
    if len(arguments) != 4:
        raise ValueError(
            f"Expected 4 arguments in smart rest template. Got {len(arguments)}"
        )
    logger.debug("Arguments: %s", arguments)
    transmit_rate = int(arguments[2])
    polling_rate = int(arguments[3])
    logger.debug("transmitRate: %d, pollingRate: %d", transmit_rate, polling_rate)

    # Get device configuration
    logger.info("Read mapping toml from %s", CONFIG_PATH)
    modbus_config = toml.load(CONFIG_PATH)
    logger.debug("Current configuration: %s", modbus_config)

    # Update configuration
    modbus_config["modbus"]["transmitinterval"] = transmit_rate
    modbus_config["modbus"]["pollinterval"] = polling_rate

    # Save to file
    logger.info("Saving new configuration to %s", CONFIG_PATH)
    with open(CONFIG_PATH, "w", encoding="utf8") as f:
        toml.dump(modbus_config, f)
    logger.info("New configuration saved to %s", CONFIG_PATH)

    # Update managedObject
    logger.debug("Updating managedObject with new configuration")

    config = {
        "transmitRate": transmit_rate,
        "pollingRate": polling_rate,
    }
    mqtt_publish(
        topic="te/device/main///twin/c8y_ModbusConfiguration",
        payload=json.dumps(config),
        qos=1,
        retain=True,
        hostname=BROKER,
        port=PORT,
        client_id=CLIENT_ID,
    )

except Exception as e:
    logger.error("Error: %s", e)
    sys.exit(1)
