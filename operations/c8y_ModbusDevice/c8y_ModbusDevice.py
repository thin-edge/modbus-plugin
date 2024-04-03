#!/usr/bin/env python3
import logging
import subprocess
import sys
import requests
import toml


def get_tedge_id():
    try:
        # Run the command and capture the output
        result = subprocess.run(
            ["tedge", "config", "get", "device.id"],
            capture_output=True,
            text=True,
            check=True,
        )

        # Access the output value
        device_id = result.stdout.strip()

        return device_id
    except subprocess.CalledProcessError as proc_err:
        raise proc_err


def update_or_create_device_mapping(
    mapping, child_name, modbus_address, modbus_server, modbus_type, new_mapping
):
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
            measurement_mapping[
                "templatestring"
            ] = f'{{"{meas_type}":{{"{meas_series}":%%}}}}'
            device["registers"][i]["measurementmapping"] = measurement_mapping

    return device


logger = logging.getLogger("c8y_ModbusDevice")
logging.basicConfig(
    filename="/var/log/tedge/c8y_ModbusDevice.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger.info("New c8y_ModbusDevice operation")

CONFIG_PATH = "/etc/tedge/plugins/modbus/devices.toml"

# TODO: Get values from thin-edge.io directly
BROKER = "127.0.0.1"

try:
    # Check and store arguments
    arguments = sys.argv[1].split(",")
    if len(arguments) != 8:
        raise ValueError(
            "Expected 8 arguments in smart rest template. Got "
            + str(len(arguments))
            + "."
        )
    modbus_type = arguments[2]  # Only works for TCP.
    modbus_address = arguments[3]
    child_name = arguments[4]
    modbus_server = arguments[5]
    deviceId = arguments[6]
    mapping_path = arguments[7]

    # Fail if modbus_type is not TCP
    if modbus_type != "TCP":
        raise ValueError("Expected modbus_type to be TCP. Got " + modbus_type + ".")

    # Update external id of child device
    logger.debug("Create external id for child device %s", deviceId)
    url = f"http://{BROKER}:8001/c8y/identity/globalIds/{deviceId}/externalIds"
    tedge_id = get_tedge_id()
    data = {"externalId": f"{tedge_id}:device:{child_name}", "type": "c8y_Serial"}
    response = requests.post(url, json=data, timeout=60)
    if response.status_code != 201:
        raise Exception(
            f"Error creating external id for child device with id {deviceId}. "
            f"Got response {response.status_code} from {url}. Expected 201."
        )
    logger.info(
        "Created external id for child device with id %s to %s",
        deviceId,
        data["externalId"],
    )

    # Get the mapping json via rest
    url = f"http://{BROKER}:8001/c8y{mapping_path}"
    logger.debug("Getting mapping json from %s", url)
    response = requests.get(url, timeout=60)
    logger.info("Got mapping json from %s with response %d", url, response.status_code)
    if response.status_code != 200:
        raise Exception(
            f"Error getting mapping at {mapping_path}. "
            f"Got response {response.status_code} from {url}. Expected 200."
        )
    new_mapping = response.json()

    # Read the mapping toml from pathToConfig
    logger.debug("Reading mapping toml from %s", CONFIG_PATH)
    mapping = toml.load(CONFIG_PATH)
    logger.info("Read mapping toml from %s", CONFIG_PATH)

    # Update or create device data for the device with the same childName
    logger.debug(
        "Updating or creating device data for device with childName %s", child_name
    )
    update_or_create_device_mapping(
        mapping, child_name, modbus_address, modbus_server, modbus_type, new_mapping
    )

    logger.debug("Created mapping toml: %s", mapping)

    # Store the mapping toml:
    logger.debug("Storing mapping toml at %s", CONFIG_PATH)

    tomlString = toml.dumps(mapping)
    with open(CONFIG_PATH, "w", encoding="utf8") as tomlFile:
        tomlFile.write(tomlString)
    logger.info("Stored mapping toml at %s", CONFIG_PATH)
except Exception as e:
    print("Error: %s", e, file=sys.stderr)
    sys.exit(1)
