#!/usr/bin/python3
# coding=utf-8
import json
import struct
import sys
from datetime import datetime, timezone

topics = {
    'measurement': 'te/device/CHILD_ID///m/',
    'event': 'te/device/CHILD_ID///e/',
    'alarm': 'te/device/CHILD_ID///a/'
}


class MappedMessage:
    topic: str = ''
    data: str = ''

    def __init__(self, data, topic):
        self.topic = topic
        self.data = data


class ModbusMapper:
    device = None

    # store data to be able to compare them later
    data = {'hr': {}, 'ir': {}, 'co': {}, 'di': {}}

    def __init__(self, device):
        self.device = device

    def validate(self, registerdef):
        startbit = registerdef['startbit']
        fieldlength = registerdef['nobits']
        if fieldlength > 64:
            raise Exception(
                f'definition of field length too long ({fieldlength}) for register {registerdef["number"]} at {startbit}')
        if registerdef.get('datatype') == 'float' and fieldlength not in (16, 32, 64):
            raise Exception('float values must have a length of 16, 32 or 64')

    def parse_int(self, buffer, signed, mask):
        fieldlength = mask.bit_length()
        is_negative = buffer >> (fieldlength - 1) & 0x01
        if signed and is_negative:
            value = -(((buffer ^ mask) + 1) & mask)
        else:
            value = buffer & mask
        return value

    def parse_float(self, buffer, fieldlengt):
        formats = {16: 'e', 32: 'f', 64: 'd'}
        return struct.unpack(formats[fieldlengt], buffer.to_bytes(int(fieldlengt / 8), sys.byteorder))[0]

    def mapregister(self, readregister, registerdef):
        messages = []
        startbit = registerdef['startbit']
        fieldlength = registerdef['nobits']
        is_little_endian = registerdef.get('littleendian') or False
        is_litte_word_endian = self.device.get('littlewordendian') or False
        registertype = 'ir' if (registerdef.get('input') or False) else 'hr'
        registerkey = f'{registerdef["number"]}:{registerdef["startbit"]}'
        self.validate(registerdef)
        # concat the registers in case we need to read across multiple registers
        buffer = self.buffer_register(readregister, is_little_endian, is_litte_word_endian)
        buflength = len(readregister) * 16
        # shift and mask for the cases where the startbit > 0 and we are not reading the whole register as value
        buffer = (buffer >> (buflength - (startbit + fieldlength)))

        i = 1
        mask = 1
        while i < fieldlength:
            mask = ((mask << 1) + 0x1)
            i = i + 1

        buffer = buffer & mask
        if registerdef.get('datatype') == 'float':
            value = self.parse_float(buffer, fieldlength)
        else:
            value = self.parse_int(buffer, registerdef.get('signed'), mask)

        if registerdef.get('measurementmapping') is not None:
            value = value * (registerdef.get('multiplier') or 1) * (
                    10 ** (registerdef.get('decimalshiftright') or 0)) / (
                            registerdef.get('divisor') or 1)
            data = registerdef['measurementmapping']['templatestring'].replace('%%', str(value))
            messages.append(MappedMessage(data, topics['measurement'].replace('CHILD_ID', self.device.get('name'))))
        if registerdef.get('alarmmapping') is not None:
            messages.extend(self.checkalarm(value, registerdef.get('alarmmapping'), registertype, registerkey))
        if registerdef.get('eventmapping') is not None:
            messages.extend(self.checkevent(value, registerdef.get('eventmapping'), registertype, registerkey))
        self.data[registertype][registerkey] = value
        return messages

    def mapcoil(self, bits, coildefinition):
        messages = []
        registertype = 'di' if (coildefinition.get('input') or False) else 'co'
        registerkey = coildefinition["number"]
        value = 1 if bits[0] else 0
        if coildefinition.get('alarmmapping') is not None:
            messages.extend(self.checkalarm(value, coildefinition.get('alarmmapping'), registertype, registerkey))
        if coildefinition.get('eventmapping') is not None:
            messages.extend(self.checkevent(value, coildefinition.get('eventmapping'), registertype, registerkey))
        self.data[registertype][registerkey] = value
        return messages

    def checkalarm(self, value, alarmmapping, registertype, registerkey):
        messages = []
        old_data = self.data.get(registertype).get(registerkey)
        # raise alarm if bit is 1
        if (old_data is None or old_data == 0) and value > 0:
            severity = alarmmapping['severity'].lower()
            alarmtype = alarmmapping['type']
            text = alarmmapping['text']
            topic = topics['alarm']
            topic = topic.replace('CHILD_ID', self.device.get('name'))
            topic = topic.replace('SEVERITY', severity)
            topic = topic.replace('TYPE', alarmtype)
            data = {'text': text, 'time': datetime.now(timezone.utc).isoformat()}
            messages.append(MappedMessage(json.dumps(data), topic))
        return messages

    def checkevent(self, value, eventmapping, registertype, registerkey):
        messages = []
        old_data = self.data.get(registertype).get(registerkey)
        # raise event if calue changed
        if old_data is None or old_data != value:
            eventtype = eventmapping['type']
            text = eventmapping['text']
            topic = topics['event']
            topic = topic.replace('CHILD_ID', self.device.get('name'))
            topic = topic.replace('TYPE', eventtype)
            data = {'text': text, 'time': datetime.now(timezone.utc).isoformat()}
            messages.append(MappedMessage(json.dumps(data), topic))
        return messages

    @staticmethod
    def buffer_register(register: list, litte_endian, is_litte_word_endian):
        buf = 0x00

        if is_litte_word_endian:
            for reg in reversed(register):
                buf = (buf << 16) | reg if not litte_endian else (reg >> 8) | (reg << 8)
        else:
            for reg in register:
                buf = (buf << 16) | reg if not litte_endian else (reg >> 8) | (reg << 8)

        return buf
