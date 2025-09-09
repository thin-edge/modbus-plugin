#!/usr/bin/env python3
"""Cumulocity IoT ModbusConfiguration operation handler"""
import json
import logging
import toml
from paho.mqtt.publish import single as mqtt_publish

from .context import Context

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def run(arguments, context: Context):
    """Run c8y_ModbusConfiguration operation handler"""
    if len(arguments) != 4:
        raise ValueError(
            f"Expected 4 arguments in smart rest template. Got {len(arguments)}"
        )
    # Get device configuration
    modbus_config = context.base_config
    loglevel = modbus_config["modbus"]["loglevel"] or "INFO"
    logger.setLevel(getattr(logging, loglevel.upper(), logging.INFO))
    logger.info("New c8y_ModbusConfiguration operation")
    logger.debug("Current configuration: %s", modbus_config)
    transmit_rate = int(arguments[2])
    polling_rate = int(arguments[3])
    logger.debug("transmitRate: %d, pollingRate: %d", transmit_rate, polling_rate)

    # Update configuration
    modbus_config["modbus"]["transmitinterval"] = transmit_rate
    modbus_config["modbus"]["pollinterval"] = polling_rate

    # Save to file
    logger.info("Saving new modbus configuration to %s", context.base_config_path)
    with open(context.base_config_path, "w", encoding="utf8") as f:
        toml.dump(modbus_config, f)

    # Update managedObject
    logger.debug("Updating managedObject with new configuration")

    config = {
        "transmitRate": transmit_rate,
        "pollingRate": polling_rate,
    }
    # pylint: disable=duplicate-code
    mqtt_publish(
        topic="te/device/main///twin/c8y_ModbusConfiguration",
        payload=json.dumps(config),
        qos=1,
        retain=True,
        hostname=context.broker,
        port=context.port,
        client_id="c8y_ModbusConfiguration-operation-client",
    )
