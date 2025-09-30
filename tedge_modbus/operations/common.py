"""Common helpers for Modbus operation handlers."""

from __future__ import annotations

import json
import logging

import toml
from pymodbus.client import ModbusSerialClient, ModbusTcpClient


def parse_json_arguments(arguments: str | list[str]) -> dict:
    """Parse JSON arguments which may be a string or list of segments.

    Raises ValueError on invalid JSON.
    """
    if isinstance(arguments, str):
        raw = arguments
    else:
        raw = arguments[0] if len(arguments) == 1 else ",".join(arguments)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as err:
        raise ValueError(f"Invalid JSON payload: {err}") from err


def resolve_target_device(
    ip_address: str, slave_id: int, devices_path
) -> tuple[dict, str]:
    """Resolve device connection parameters from ip or devices.toml.

    Returns (target_device, protocol).
    """
    if ip_address:
        ip = ip_address or "127.0.0.1"
        protocol = "TCP"
        target_device = {
            "protocol": "TCP",
            "ip": ip,
            "port": 502,
            "address": slave_id,
        }
    else:
        devices_cfg = toml.load(devices_path)
        devices = devices_cfg.get("device", []) or []
        target_device = next(
            (d for d in devices if d.get("address") == slave_id), None
        ) or next((d for d in devices if d.get("protocol") == "TCP"), None)
        if target_device is None:
            raise ValueError(f"No suitable device found in {devices_path}")
        protocol = target_device.get("protocol")
    return target_device, protocol  # type: ignore[return-value]


def backfill_serial_defaults(
    target_device: dict, protocol: str, base_config: dict
) -> None:
    """For RTU devices, backfill serial settings from base config if missing."""
    if protocol == "RTU":
        serial_defaults = base_config.get("serial") or {}
        for key in ["port", "baudrate", "stopbits", "parity", "databits"]:
            if target_device.get(key) is None and key in serial_defaults:
                target_device[key] = serial_defaults[key]


def build_modbus_client(target_device: dict, protocol: str):
    """Create a pymodbus client for given target and protocol."""
    if protocol == "TCP":
        return ModbusTcpClient(
            host=target_device["ip"],
            port=target_device["port"],
            auto_open=True,
            auto_close=True,
            debug=True,
        )
    if protocol == "RTU":
        return ModbusSerialClient(
            port=target_device["port"],
            baudrate=target_device["baudrate"],
            stopbits=target_device["stopbits"],
            parity=target_device["parity"],
            bytesize=target_device["databits"],
        )
    raise ValueError("Expected protocol to be RTU or TCP. Got " + str(protocol) + ".")


def close_client_quietly(client) -> None:
    """Close a pymodbus client and ignore any exceptions."""
    try:
        client.close()
    except Exception:
        pass


def prepare_client(
    ip_address: str,
    slave_id: int,
    devices_path,
    base_config: dict,
):
    """Resolve target device, backfill defaults, and build a Modbus client."""
    target_device, protocol = resolve_target_device(ip_address, slave_id, devices_path)
    backfill_serial_defaults(target_device, protocol, base_config)
    return build_modbus_client(target_device, protocol)


def apply_loglevel(logger, base_config: dict) -> None:
    """Apply log level from base configuration to given logger."""
    loglevel = base_config["modbus"].get("loglevel") or "INFO"
    logger.setLevel(getattr(logging, loglevel.upper(), logging.INFO))


def parse_register_params(payload: dict) -> dict:
    """Parse and validate register operation parameters into a single dict.

    Returns a dict with keys: ip_address, slave_id, register, start_bit, num_bits, write_value.
    """
    ip_address = (payload.get("ipAddress") or "").strip()
    try:
        return {
            "ip_address": ip_address,
            "slave_id": int(payload["address"]),
            "register": int(payload["register"]),
            "start_bit": int(payload.get("startBit", 0)),
            "num_bits": int(payload.get("noBits", 16)),
            "write_value": int(payload["value"]),
        }
    except KeyError as err:
        raise ValueError(f"Missing required field: {err}") from err
    except (TypeError, ValueError) as err:
        raise ValueError(f"Invalid numeric field: {err}") from err


def compute_masked_value(
    current_value: int, start_bit: int, num_bits: int, write_value: int
) -> int:
    """Validate bit-field and compute new register value with masked bits applied."""
    if start_bit < 0 or num_bits <= 0 or start_bit + num_bits > 16:
        raise ValueError(
            "startBit and noBits must define a range within a 16-bit register"
        )
    max_value = (1 << num_bits) - 1
    if write_value < 0 or write_value > max_value:
        raise ValueError(f"value must be within 0..{max_value} for noBits={num_bits}")
    mask = ((1 << num_bits) - 1) << start_bit
    return (current_value & ~mask) | ((write_value << start_bit) & mask)
