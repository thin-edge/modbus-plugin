# pylint: disable=duplicate-code
"""Modbus Write Coil Status operation handler"""

import logging

from pymodbus.exceptions import ConnectionException
from .context import Context
from .common import (
    parse_json_arguments,
    prepare_client,
    apply_loglevel,
    close_client_quietly,
    extract_device_from_topic,
    _match_from_metrics,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def run(arguments: str | list[str], topic: str | None = None) -> None:
    """Run set coil operation handler

    Supports two payload formats:

    1. Explicit address format (full coil details):
        {
            "input": false,
            "address": < Fieldbusaddress >,
            "coil": < coilnumber >,
            "value": < 0 | 1 >
        }

    2. New format (name-based):
        {
            "timestamp": "2025-09-23T00:00:00Z",
            "uuid": "device-id",
            "metrics": [{
                "name": "<name>_xxxxxxxx",
                "timestamp": "2025-09-23T01:00:00Z",
                "value": 0 or 1
            }]
        }
        Requires topic: te/device/<device-id>///cmd/modbus_SetCoil/<mapper-id>
    """
    payload = parse_json_arguments(arguments)
    context = Context()
    modbus_config = context.base_config
    apply_loglevel(logger, modbus_config)
    logger.info("Processing set coil operation")

    # Determine format and extract parameters
    if "metrics" in payload and topic:
        params = _process_new_format_coil(payload, topic, context)
    else:
        params = _process_explicit_format_coil(payload)

    # Prepare client
    client = prepare_client(
        params["ip_address"],
        params["slave_id"],
        context.config_dir / "devices.toml",
        modbus_config,
    )

    try:
        result = client.write_coil(
            address=params["coil_number"],
            value=bool(params["value"]),
            slave=params["slave_id"],
        )
        if result.isError():
            raise RuntimeError(
                f"Failed to write coil {params['coil_number']}: {result}"
            )
        logger.info(
            "Wrote %s to coil %d on slave %d",
            bool(params["value"]),
            params["coil_number"],
            params["slave_id"],
        )
    except ConnectionException as err:
        logger.error(
            "Connection error while writing to slave %d: %s",
            params["slave_id"],
            err,
        )
        raise
    finally:
        close_client_quietly(client)


def _process_new_format_coil(payload: dict, topic: str, context) -> dict:
    """Process new format coil payload with metrics array."""
    logger.info("Processing new format payload with metrics array")
    device_name = extract_device_from_topic(topic)
    if not device_name:
        raise ValueError(f"Could not extract device name from topic: {topic}")

    coil_config, target_device, coil_id, write_value = _match_from_metrics(
        payload,
        device_name,
        context.config_dir / "devices.toml",
        "coils",
        "name",
        int,
    )

    if not coil_config:
        raise ValueError("Could not match any coil for metrics in payload")
    if not target_device:
        raise ValueError(f"Could not find device '{device_name}' in devices.toml")

    logger.info("Matched CoilID: %s, Value: %s", coil_id, write_value)

    coil_number = coil_config.get("number")
    if coil_number is None:
        raise ValueError(
            f"Coil configuration missing 'number' field for name '{coil_id}'"
        )

    value_int = int(write_value)
    if value_int not in (0, 1):
        raise ValueError("Coil value must be 0 or 1")

    return {
        "ip_address": target_device.get("ip", ""),
        "slave_id": target_device.get("address"),
        "coil_number": coil_number,
        "value": value_int,
    }


def _process_explicit_format_coil(payload: dict) -> dict:
    """Process explicit address format coil payload."""
    logger.info("Processing explicit address format payload")
    try:
        value = int(payload["value"])
        if value not in (0, 1):
            raise ValueError("value must be 0 or 1 for a coil write")

        return {
            "ip_address": payload.get("ipAddress", ""),
            "slave_id": int(payload["address"]),
            "coil_number": int(payload["coil"]),
            "value": value,
        }
    except KeyError as err:
        raise ValueError(f"Missing required field: {err}") from err
    except (TypeError, ValueError) as err:
        raise ValueError(f"Invalid numeric field: {err}") from err
