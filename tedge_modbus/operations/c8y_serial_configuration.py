#!/usr/bin/env python3
"""Cumulocity SerialConfiguration operation handler"""
import json
import logging
import toml
from paho.mqtt.publish import single as mqtt_publish

from .context import Context

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


# pylint: disable=duplicate-code
def run(arguments, context: Context):
    """Run c8y_SerialConfiguration operation handler"""
    if len(arguments) != 1:
        raise ValueError(f"Expected 1 argument. Got {len(arguments)}")
    # Get device configuration
    modbus_config = context.base_config
    loglevel = modbus_config["modbus"]["loglevel"] or "INFO"
    logger.setLevel(getattr(logging, loglevel.upper(), logging.INFO))
    logger.info("New c8y_SerialConfiguration operation")
    logger.debug("Current configuration: %s", modbus_config)
    data = json.loads(arguments[0])
    baud_rate = data["baudRate"]
    stop_bits = data["stopBits"]
    parity = data["parity"]
    data_bits = data["dataBits"]
    logger.debug(
        "baudRate: %d, stopBits: %d, parity: %s, dataBits: %d",
        baud_rate,
        stop_bits,
        parity,
        data_bits,
    )

    # Update configuration
    modbus_config["serial"]["baudrate"] = baud_rate
    modbus_config["serial"]["stopbits"] = stop_bits
    modbus_config["serial"]["parity"] = parity
    modbus_config["serial"]["databits"] = data_bits

    # Save to file
    logger.info("Saving new serial configuration to %s", context.base_config_path)
    with open(context.base_config_path, "w", encoding="utf8") as f:
        toml.dump(modbus_config, f)

    # Update managedObject
    logger.debug("Updating managedObject with new configuration")
    # pylint: disable=duplicate-code
    config = {
        "baudRate": baud_rate,
        "stopBits": stop_bits,
        "parity": parity,
        "dataBits": data_bits,
    }
    mqtt_publish(
        topic="te/device/main///twin/c8y_SerialConfiguration",
        payload=json.dumps(config),
        qos=1,
        retain=True,
        hostname=context.broker,
        port=context.port,
        client_id="c8y_SerialConfiguration-operation-client",
    )
