#!/usr/bin/env python3
"""Modbus mapper"""
import json
import struct
import sys
import math
from datetime import datetime, timezone
from dataclasses import dataclass

topics = {
    "measurement": "te/device/CHILD_ID///m/",
    "event": "te/device/CHILD_ID///e/",
    "alarm": "te/device/CHILD_ID///a/",
}


@dataclass
class MappedMessage:
    """Mapped message"""

    data: str = ""
    topic: str = ""


class ModbusMapper:
    """Modbus mapper"""

    device = None

    # store data to be able to compare them later
    data = {"hr": {}, "ir": {}, "co": {}, "di": {}}

    def __init__(self, device):
        self.device = device

    def validate(self, register_def):
        """Validate definition"""
        start_bit = register_def["startbit"]
        field_len = register_def["nobits"]
        if field_len > 64:
            raise ValueError(
                f"definition of field length too long ({field_len}) "
                f'for register {register_def["number"]} at {start_bit}'
            )
        if register_def.get("datatype") == "float" and field_len not in (16, 32, 64):
            raise ValueError("float values must have a length of 16, 32 or 64")

    def parse_int(self, buffer, signed, mask):
        """parse value to an integer"""
        field_len = mask.bit_length()
        is_negative = buffer >> (field_len - 1) & 0x01
        if signed and is_negative:
            value = -(((buffer ^ mask) + 1) & mask)
        else:
            value = buffer & mask
        return value

    def parse_float(self, buffer, field_len):
        """parse value to a float"""
        formats = {16: "e", 32: "f", 64: "d"}
        return struct.unpack(
            formats[field_len], buffer.to_bytes(int(field_len / 8), sys.byteorder)
        )[0]

    def map_register(self, read_register, register_def):
        """Map register"""
        # pylint: disable=too-many-locals
        messages = []
        start_bit = register_def["startbit"]
        field_len = register_def["nobits"]
        is_little_endian = register_def.get("littleendian") or False
        is_little_word_endian = self.device.get("littlewordendian") or False
        register_type = "ir" if register_def.get("input") else "hr"
        register_key = f'{register_def["number"]}:{register_def["startbit"]}'
        self.validate(register_def)
        # concat the registers in case we need to read across multiple registers
        buffer = self.buffer_register(
            read_register, is_little_endian, is_little_word_endian
        )
        buffer_len = len(read_register) * 16
        # shift and mask for the cases where the start_bit > 0 and
        # we are not reading the whole register as value
        buffer = buffer >> (buffer_len - (start_bit + field_len))

        i = 1
        mask = 1
        while i < field_len:
            mask = (mask << 1) + 0x1
            i = i + 1

        buffer = buffer & mask
        if register_def.get("datatype") == "float":
            value = self.parse_float(buffer, field_len)
        else:
            value = self.parse_int(buffer, register_def.get("signed"), mask)

        if register_def.get("measurementmapping") is not None:
            scaled_value = (
                value
                * (register_def.get("multiplier") or 1)
                * (10 ** (register_def.get("decimalshiftright") or 0))
                / (register_def.get("divisor") or 1)
            )

            on_change = register_def.get("on_change", False)

            last_value = self.data.get(register_type, {}).get(register_key)

            if not on_change or last_value is None or \
                (isinstance(scaled_value, float) and not math.isclose(scaled_value, last_value)) or \
                (not isinstance(scaled_value, float) and last_value != scaled_value):
                data = register_def["measurementmapping"]["templatestring"].replace(
                    "%%", str(scaled_value)
                )
                messages.append(
                    MappedMessage(
                        data,
                        topics["measurement"].replace(
                            "CHILD_ID", self.device.get("name")
                        ),
                    )
                )

                self.data.setdefault(register_type, {})[register_key] = scaled_value

            value = scaled_value
        if register_def.get("alarmmapping") is not None:
            messages.extend(
                self.check_alarm(
                    value, register_def.get("alarmmapping"), register_type, register_key
                )
            )
        if register_def.get("eventmapping") is not None:
            messages.extend(
                self.check_event(
                    value, register_def.get("eventmapping"), register_type, register_key
                )
            )

        if register_def.get("measurementmapping") is None:
            self.data.setdefault(register_type, {})[register_key] = value
        return messages

    def map_coil(self, bits, coil_definition):
        """Map coil"""
        messages = []
        register_type = "di" if coil_definition.get("input") else "co"
        register_key = coil_definition["number"]
        value = 1 if bits[0] else 0
        if coil_definition.get("alarmmapping") is not None:
            messages.extend(
                self.check_alarm(
                    value,
                    coil_definition.get("alarmmapping"),
                    register_type,
                    register_key,
                )
            )
        if coil_definition.get("eventmapping") is not None:
            messages.extend(
                self.check_event(
                    value,
                    coil_definition.get("eventmapping"),
                    register_type,
                    register_key,
                )
            )
        self.data[register_type][register_key] = value
        return messages

    def check_alarm(self, value, alarm_mapping, register_type, register_key):
        """Check alarm"""
        messages = []
        old_data = self.data.get(register_type).get(register_key)
        # raise alarm if bit is 1
        if (old_data is None or old_data == 0) and value > 0:
            severity = alarm_mapping["severity"].lower()
            alarm_type = alarm_mapping["type"]
            text = alarm_mapping["text"]
            topic = topics["alarm"]
            topic = topic.replace("CHILD_ID", self.device.get("name"))
            topic = topic.replace("SEVERITY", severity)
            topic = topic.replace("TYPE", alarm_type)
            data = {"text": text, "time": datetime.now(timezone.utc).isoformat()}
            messages.append(MappedMessage(json.dumps(data), topic))
        return messages

    def check_event(self, value, event_mapping, register_type, register_key):
        """Check event"""
        messages = []
        old_data = self.data.get(register_type).get(register_key)
        # raise event if value changed
        if old_data is None or old_data != value:
            eventtype = event_mapping["type"]
            text = event_mapping["text"]
            topic = topics["event"]
            topic = topic.replace("CHILD_ID", self.device.get("name"))
            topic = topic.replace("TYPE", eventtype)
            data = {"text": text, "time": datetime.now(timezone.utc).isoformat()}
            messages.append(MappedMessage(json.dumps(data), topic))
        return messages

    @staticmethod
    def buffer_register(register: list, little_endian, is_little_word_endian):
        """Buffer register"""
        buf = 0x00

        if is_little_word_endian:
            for reg in reversed(register):
                buf = (
                    (buf << 16) | reg if not little_endian else (reg >> 8) | (reg << 8)
                )
        else:
            for reg in register:
                buf = (
                    (buf << 16) | reg if not little_endian else (reg >> 8) | (reg << 8)
                )

        return buf
