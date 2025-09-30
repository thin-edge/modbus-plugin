# pylint: disable=duplicate-code
"""Modbus Write register status operation handler"""
import logging

from pymodbus.exceptions import ConnectionException
from .context import Context
from .common import (
    parse_json_arguments,
    prepare_client,
    apply_loglevel,
    close_client_quietly,
    parse_register_params,
    compute_masked_value,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def run(arguments: str | list[str]) -> None:
    """Run set register operation handler
    Expected arguments (JSON):
        {
        "input": false,
        "ipAddress": <ip address or empty>,
        "address": <Fieldbus address>,
        "register": <register number>,
        "startBit": <start bit>,
        "noBits": <number of bits>,
        "value": <register value>
      }
    Parse JSON arguments. Depending on the caller, we may receive the JSON as a single
    string or a list of comma-split segments. Handle both cases robustly."""
    payload = parse_json_arguments(arguments)

    # Create context with default config directory
    context = Context()

    # Load configs and set log level
    modbus_config = context.base_config
    apply_loglevel(logger, modbus_config)
    logger.info("New set register operation")

    # Parse required fields from JSON
    params = parse_register_params(payload)

    # Prepare client (resolve target, backfill defaults, build client)
    client = prepare_client(
        params["ip_address"],
        params["slave_id"],
        context.config_dir / "devices.toml",
        modbus_config,
    )

    # Validate and compute new value

    try:
        # Read current register value
        read_resp = client.read_holding_registers(
            address=params["register"], count=1, slave=params["slave_id"]
        )
        if read_resp.isError():
            raise RuntimeError(
                f"Failed to read register {params['register']}: {read_resp}"
            )
        current_value = read_resp.registers[0] & 0xFFFF
        new_value = compute_masked_value(
            current_value,
            params["start_bit"],
            params["num_bits"],
            params["write_value"],
        )

        # Write back register
        write_resp = client.write_register(
            address=params["register"], value=new_value, slave=params["slave_id"]
        )
        if write_resp.isError():
            raise RuntimeError(
                f"Failed to write register {params['register']}: {write_resp}"
            )
        logger.info(
            "Updated register %d (bits %d..%d) from 0x%04X to 0x%04X on slave %d",
            params["register"],
            params["start_bit"],
            params["start_bit"] + params["num_bits"] - 1,
            current_value,
            new_value,
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
