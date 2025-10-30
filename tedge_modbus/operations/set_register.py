# pylint: disable=duplicate-code
"""Modbus Write register status operation handler"""

import logging
import struct
import sys

from pymodbus.exceptions import ConnectionException
from .context import Context
from .common import (
    parse_json_arguments,
    prepare_client,
    apply_loglevel,
    close_client_quietly,
    parse_register_params,
    compute_masked_value,
    extract_device_from_topic,
    _match_from_metrics,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def run(arguments: str | list[str], topic: str | None = None) -> None:
    """Run set register operation handler
    Supports two payload formats:
    1. Explicit address c8y format (full register details)
    2. New format (name-based)
    """
    payload = parse_json_arguments(arguments)
    context = Context()
    modbus_config = context.base_config
    apply_loglevel(logger, modbus_config)
    logger.info("Processing set register operation")

    # Determine format and extract parameters
    if "metrics" in payload and topic:
        params = _process_new_format_register(payload, topic, context)
    else:
        params = _process_explicit_format_register(payload)

    # Prepare client
    client = prepare_client(
        params["ip_address"],
        params["slave_id"],
        context.config_dir / "devices.toml",
        modbus_config,
    )

    try:
        if params["is_float"]:
            _write_float_registers(client, params)
        else:
            _write_integer_register(client, params)
    except ConnectionException as err:
        logger.error(
            "Connection error while writing to slave %d: %s",
            params["slave_id"],
            err,
        )
        raise
    finally:
        close_client_quietly(client)


def _process_new_format_register(payload: dict, topic: str, context) -> dict:
    """Process new format register payload with metrics array"""
    logger.info("Processing new format payload with metrics array")
    device_name = extract_device_from_topic(topic)
    if not device_name:
        raise ValueError(f"Could not extract device name from topic: {topic}")

    register_config, target_device, register_id, write_value = _match_from_metrics(
        payload,
        device_name,
        context.config_dir / "devices.toml",
        "registers",
        "name",
        float,
    )

    if not register_config:
        raise ValueError("Could not match any register for metrics in payload")
    if not target_device:
        raise ValueError(f"Could not find device '{device_name}' in devices.toml")

    logger.info("Matched RegisterID: %s, Value: %s", register_id, write_value)

    register_num = register_config.get("number")
    if register_num is None:
        raise ValueError(
            f"Register configuration missing 'number' field for name '{register_id}'"
        )

    is_float = register_config.get("datatype") == "float"
    params = {
        "ip_address": target_device.get("ip", ""),
        "slave_id": target_device.get("address"),
        "register": register_num,
        "start_bit": register_config.get("startbit", 0),
        "num_bits": register_config.get("nobits", 16),
        "is_float": is_float,
    }

    if is_float:
        params["write_value"] = write_value
        params["little_word_endian"] = target_device.get("littlewordendian", False)
    else:
        params["write_value"] = int(write_value)

    return params


def _process_explicit_format_register(payload: dict) -> dict:
    """Process explicit address format register payload."""
    logger.info("Processing explicit address format payload")
    params = parse_register_params(payload)
    params["is_float"] = False
    return params


def _write_float_registers(client, params: dict) -> None:
    """Write float values to multiple registers."""
    register_pairs = _float_to_register_pairs(
        params["write_value"],
        params["num_bits"],
        params.get("little_word_endian", False),
    )

    logger.info(
        "Writing float value %s to registers starting at %d",
        params["write_value"],
        params["register"],
    )

    write_resp = client.write_registers(
        address=params["register"],
        values=register_pairs,
        slave=params["slave_id"],
    )
    if write_resp.isError():
        raise RuntimeError(
            f"Failed to write registers {params['register']}: {write_resp}"
        )

    for i, reg_value in enumerate(register_pairs):
        logger.info("Wrote 0x%04X to register %d", reg_value, params["register"] + i)


def _write_integer_register(client, params: dict) -> None:
    """Write integer value to register with bit masking."""
    # Read current register value first
    read_resp = client.read_holding_registers(
        address=params["register"], count=1, slave=params["slave_id"]
    )
    if read_resp.isError():
        raise RuntimeError(f"Failed to read register {params['register']}: {read_resp}")

    current_value = read_resp.registers[0] & 0xFFFF
    new_value = compute_masked_value(
        current_value,
        params["start_bit"],
        params["num_bits"],
        params["write_value"],
    )

    # Write updated value
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


def _float_to_register_pairs(
    value: float, num_bits: int = 32, little_word_endian: bool = False
) -> list[int]:
    """Convert float to register values based on datatype and endianness.

    Ensures cross-platform consistency by using sys.byteorder (same as reader).
    Handles endianness reversal to match buffer_register logic in reader.

    Args:
        value: Float value to convert
        num_bits: Number of bits (16, 32, or 64)
        little_word_endian: Whether device uses little word endian

    Returns:
        List of register values (as integers) representing the float
    """
    byte_order_suffix = ">" if sys.byteorder == "big" else "<"

    if num_bits == 32:
        packed = struct.pack(f"{byte_order_suffix}f", value)
        reg_low = struct.unpack("<H", packed[0:2])[0]
        reg_high = struct.unpack("<H", packed[2:4])[0]
        # Reverse order for little_word_endian to match reader's buffer_register logic
        return [reg_low, reg_high] if little_word_endian else [reg_high, reg_low]

    if num_bits == 16:
        packed = struct.pack(f"{byte_order_suffix}e", value)
        reg = struct.unpack(f"{byte_order_suffix}H", packed)[0]
        return [reg]

    if num_bits == 64:
        packed = struct.pack(f"{byte_order_suffix}d", value)
        regs = []
        for i in range(0, 8, 2):
            reg = struct.unpack(f"{byte_order_suffix}H", packed[i : i + 2])[0]
            regs.append(reg)

        # Similar logic to float32: reverse order if little_word_endian
        if little_word_endian:
            return list(reversed(regs))
        return regs

    raise ValueError(f"Unsupported float size: {num_bits} bits")
