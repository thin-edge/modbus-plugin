#!/usr/bin/env python3
"""Modbus Write Coil Status operation handler"""
import logging

from pymodbus.exceptions import ConnectionException
from .context import Context
from .common import (
    parse_json_arguments,
    prepare_client,
    apply_loglevel,
    close_client_quietly,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def run(arguments: str | list[str]) -> None:
    """Run set coil operation handler
    Expected arguments (JSON):
    {
        "input": false,
        "address": < Fieldbusaddress >,
        "coil": < coilnumber >,
        "value": < 0 | 1 >
    }
    Parse JSON payload"""
    payload = parse_json_arguments(arguments)

    # Create context with default config directory
    context = Context()

    # Load configs and set log level
    modbus_config = context.base_config
    apply_loglevel(logger, modbus_config)
    logger.info("New set coil operation. args=%s", arguments)

    try:
        slave_id = int(payload["address"])  # Fieldbus address
        coil_number = int(payload["coil"])  # Coil address
        value_int = int(payload["value"])  # 0 or 1
    except KeyError as err:
        raise ValueError(f"Missing required field: {err}") from err
    except (TypeError, ValueError) as err:
        raise ValueError(f"Invalid numeric field: {err}") from err

    if value_int not in (0, 1):
        raise ValueError("value must be 0 or 1 for a coil write")

    # Prepare client (resolve target, backfill defaults, build client)
    client = prepare_client(
        payload["ipAddress"],
        slave_id,
        context.config_dir / "devices.toml",
        modbus_config,
    )

    try:
        coil_value = bool(value_int)
        result = client.write_coil(
            address=coil_number,
            value=coil_value,
            slave=slave_id,
        )
        if result.isError():
            raise RuntimeError(f"Failed to write coil {coil_number}: {result}")
        logger.info(
            "Wrote %s to coil %d on slave %d", coil_value, coil_number, slave_id
        )
    except ConnectionException as err:
        logger.error("Connection error while writing to slave %d: %s", slave_id, err)
        raise
    finally:
        close_client_quietly(client)
