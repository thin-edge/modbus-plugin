#!/usr/bin/env python3
"""Cumulocity IoT Modbus device operation handler
"""
import logging
import requests
import toml

from .context import Context

logger = logging.getLogger("c8y_ModbusDevice")
logging.basicConfig(
    filename="/var/log/tedge/c8y_ModbusDevice.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def update_or_create_device_mapping(
    mapping, child_name, modbus_address, modbus_server, modbus_type, new_mapping
):
    """Update or create device mapping"""
    devices = mapping.setdefault("device", [])
    for i, device in enumerate(devices):
        if device.get("name") == child_name:
            devices[i] = get_device_from_mapping(
                child_name, modbus_address, modbus_server, modbus_type, new_mapping
            )
            return
    devices.append(
        get_device_from_mapping(
            child_name, modbus_address, modbus_server, modbus_type, new_mapping
        )
    )


def get_device_from_mapping(
    child_name, modbus_address, modbus_server, modbus_type, mapping
):
    """Get a device from a given mapping definition"""
    device = {}
    device["name"] = child_name
    device["address"] = int(modbus_address)
    device["ip"] = modbus_server
    device["port"] = 502
    device["protocol"] = modbus_type
    device["littlewordendian"] = True

    # Registers
    device["registers"] = [{}] * len(mapping["c8y_Registers"])

    for i, c8y_register in enumerate(mapping["c8y_Registers"]):
        device["registers"][i]["number"] = c8y_register["number"]
        device["registers"][i]["startbit"] = c8y_register["startBit"]
        device["registers"][i]["nobits"] = c8y_register["noBits"]
        device["registers"][i]["signed"] = c8y_register["signed"]
        device["registers"][i]["multiplier"] = c8y_register["multiplier"]
        device["registers"][i]["divisor"] = c8y_register["divisor"]
        device["registers"][i]["decimalshiftright"] = c8y_register["offset"]
        device["registers"][i]["input"] = c8y_register["input"]
        # Measurements
        if "measurementMapping" in c8y_register:
            # device["registers"][i]['measurementmapping'] = {}
            measurement_mapping = {}
            meas_type = c8y_register["measurementMapping"]["type"]
            meas_series = c8y_register["measurementMapping"]["series"]
            measurement_mapping["templatestring"] = (
                f'{{"{meas_type}":{{"{meas_series}":%%}}}}'
            )
            device["registers"][i]["measurementmapping"] = measurement_mapping

    return device


def run(arguments, context: Context):
    """main"""
    logger.info("New c8y_ModbusDevice operation")
    # Check and store arguments
    if len(arguments) != 8:
        raise ValueError(
            "Expected 8 arguments in smart rest template. Got "
            + str(len(arguments))
            + "."
        )
    config_path = context.config_dir / "devices.toml"
    modbus_type = arguments[2]  # Only works for TCP.
    modbus_address = arguments[3]
    child_name = arguments[4]
    modbus_server = arguments[5]
    device_id = arguments[6]
    mapping_path = arguments[7]

    # Fail if modbus_type is not TCP
    if modbus_type != "TCP":
        raise ValueError("Expected modbus_type to be TCP. Got " + modbus_type + ".")

    # Update external id of child device
    logger.debug("Create external id for child device %s", device_id)
    url = f"{context.c8y_proxy}/identity/globalIds/{device_id}/externalIds"
    data = {
        "externalId": f"{context.device_id}:device:{child_name}",
        "type": "c8y_Serial",
    }
    response = requests.post(url, json=data, timeout=60)
    if response.status_code != 201:
        raise ValueError(
            f"Error creating external id for child device with id {device_id}. "
            f"Got response {response.status_code} from {url}. Expected 201."
        )
    logger.info(
        "Created external id for child device with id %s to %s",
        device_id,
        data["externalId"],
    )

    # Get the mapping json via rest
    url = f"{context.c8y_proxy}{mapping_path}"
    logger.debug("Getting mapping json from %s", url)
    response = requests.get(url, timeout=60)
    logger.info("Got mapping json from %s with response %d", url, response.status_code)
    if response.status_code != 200:
        raise ValueError(
            f"Error getting mapping at {mapping_path}. "
            f"Got response {response.status_code} from {url}. Expected 200."
        )
    new_mapping = response.json()

    # Read the mapping toml from pathToConfig
    logger.debug("Reading mapping toml from %s", config_path)
    mapping = toml.load(config_path)
    logger.info("Read mapping toml from %s", config_path)

    # Update or create device data for the device with the same childName
    logger.debug(
        "Updating or creating device data for device with childName %s", child_name
    )
    update_or_create_device_mapping(
        mapping, child_name, modbus_address, modbus_server, modbus_type, new_mapping
    )

    logger.debug("Created mapping toml: %s", mapping)

    # Store the mapping toml:
    logger.debug("Storing mapping toml at %s", config_path)

    toml_str = toml.dumps(mapping)
    with open(config_path, "w", encoding="utf8") as file:
        file.write(toml_str)
    logger.info("Stored mapping toml at %s", config_path)
