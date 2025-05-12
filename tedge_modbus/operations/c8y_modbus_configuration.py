#!/usr/bin/env python3
"""Cumulocity IoT ModbusConfiguration operation handler"""
import json
import logging
import toml
from paho.mqtt.publish import single as mqtt_publish

from .context import Context

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger.info("New c8y_ModbusConfiguration operation")


def run(arguments, context: Context):
    """Run c8y_ModbusConfiguration operation handler"""
    if len(arguments) != 4:
        raise ValueError(
            f"Expected 4 arguments in smart rest template. Got {len(arguments)}"
        )
    logger.debug("Arguments: %s", arguments)
    transmit_rate = int(arguments[2])
    polling_rate = int(arguments[3])
    logger.debug("transmitRate: %d, pollingRate: %d", transmit_rate, polling_rate)

    # Get device configuration
    config_path = context.config_dir / "modbus.toml"
    logger.info("Read mapping toml from %s", config_path)
    modbus_config = toml.load(config_path)
    logger.debug("Current configuration: %s", modbus_config)

    # Update configuration
    modbus_config["modbus"]["transmitinterval"] = transmit_rate
    modbus_config["modbus"]["pollinterval"] = polling_rate

    # Save to file
    logger.info("Saving new configuration to %s", config_path)
    with open(config_path, "w", encoding="utf8") as f:
        toml.dump(modbus_config, f)
    logger.info("New configuration saved to %s", config_path)

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
        hostname=context.broker,
        port=context.port,
        client_id="c8y_ModbusConfiguration-operation-client",
    )
