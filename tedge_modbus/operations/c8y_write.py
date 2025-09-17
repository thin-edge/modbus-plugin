#!/usr/bin/env python3
"""Cumulocity IoT Modbus Write operation handler"""
import json
import logging
import toml
from paho.mqtt.publish import single as mqtt_publish

from .context import Context
from pymodbus.client import ModbusTcpClient, ModbusSerialClient
from pymodbus.exceptions import ConnectionException

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

def run(arguments, context: Context):
    """Run c8y_Write operation handler"""
    # Expected arguments (CSV):
    # [<templateId>, <deviceName>, <targetType>, <number>, <value>]
    # - targetType: "register" or "coil"
    # - number: integer address
    # - value: integer for register, boolean (0/1/true/false) for coil
    if len(arguments) < 5:
        raise ValueError(
            f"Expected at least 5 arguments in smart rest template. Got {len(arguments)}"
        )

    # Load configs and set log level
    modbus_config = context.base_config
    loglevel = modbus_config["modbus"].get("loglevel") or "INFO"
    logger.setLevel(getattr(logging, loglevel.upper(), logging.INFO))
    logger.info("New c8y_Write operation")

    device_name = arguments[1]
    target_type = arguments[2].strip().lower()
    try:
        number = int(arguments[3])
    except ValueError as err:
        raise ValueError(f"Invalid address: {arguments[3]}") from err
    value_raw = arguments[4].strip()

    # Read device definition to find connection parameters
    devices_path = context.config_dir / "devices.toml"
    devices_cfg = toml.load(devices_path)
    devices = devices_cfg.get("device", []) or []
    target_device = next((d for d in devices if d.get("name") == device_name), None)
    if target_device is None:
        raise ValueError(f"Device '{device_name}' not found in {devices_path}")

    # For RTU, backfill serial settings from base config if missing
    if target_device.get("protocol") == "RTU":
        serial_defaults = modbus_config.get("serial") or {}
        for key in ["port", "baudrate", "stopbits", "parity", "databits"]:
            if target_device.get(key) is None and key in serial_defaults:
                target_device[key] = serial_defaults[key]

    # Build Modbus client
    if target_device.get("protocol") == "TCP":
        client = ModbusTcpClient(
            host=target_device["ip"],
            port=target_device["port"],
            auto_open=True,
            auto_close=True,
            debug=True,
        )
    elif target_device.get("protocol") == "RTU":
        client = ModbusSerialClient(
            port=target_device["port"],
            baudrate=target_device["baudrate"],
            stopbits=target_device["stopbits"],
            parity=target_device["parity"],
            bytesize=target_device["databits"],
        )
    else:
        raise ValueError(
            "Expected protocol to be RTU or TCP. Got "
            + str(target_device.get("protocol"))
            + "."
        )

    slave_id = target_device["address"]

    try:
        if target_type == "register":
            try:
                register_value = int(value_raw, 0)
            except ValueError as err:
                raise ValueError(f"Invalid register value: {value_raw}") from err
            result = client.write_register(address=number, value=register_value, slave=slave_id)
            if result.isError():
                raise RuntimeError(f"Failed to write register {number}: {result}")
            logger.info("Wrote %d to register %d on device %s", register_value, number, device_name)
        elif target_type == "coil":
            truthy = {"1", "true", "on", "yes"}
            falsy = {"0", "false", "off", "no"}
            val_norm = value_raw.lower()
            if val_norm in truthy:
                coil_value = True
            elif val_norm in falsy:
                coil_value = False
            else:
                raise ValueError(f"Invalid coil value: {value_raw}")
            result = client.write_coil(address=number, value=coil_value, slave=slave_id)
            if result.isError():
                raise RuntimeError(f"Failed to write coil {number}: {result}")
            logger.info("Wrote %s to coil %d on device %s", coil_value, number, device_name)
        else:
            raise ValueError("targetType must be 'register' or 'coil'")
    except ConnectionException as err:
        logger.error("Connection error while writing to device %s: %s", device_name, err)
        raise
    finally:
        try:
            client.close()
        except Exception:  # pylint: disable=broad-except
            pass

    # # Optionally, publish an acknowledgement to Cumulocity via thin-edge (best-effort)
    # try:
    #     payload = {
    #         "device": device_name,
    #         "type": target_type,
    #         "number": number,
    #         "value": value_raw,
    #         "status": "success",
    #     }
    #     mqtt_publish(
    #         topic="te/device/main///e/c8y_ModbusWrite",
    #         payload=json.dumps(payload),
    #         qos=0,
    #         retain=False,
    #         hostname=context.broker,
    #         port=context.port,
    #         client_id="c8y_ModbusWrite-operation-client",
    #     )
    # except Exception:  # best-effort acknowledgement
    #     pass
