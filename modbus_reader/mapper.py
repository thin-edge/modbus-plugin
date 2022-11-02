import json

from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.bit_read_message import ReadBitsResponseBase
from pymodbus.register_read_message import ReadRegistersResponseBase
from datetime import datetime, timezone

decoder_func = {
    'int16': lambda d: d.decode_16bit_int(),
    'uint16': lambda d: d.decode_16bit_uint(),
    'float32': lambda d: d.decode_32bit_float(),
    'float64': lambda d: d.decode_64bit_float()
}

topics = {
    'measurement': 'tedge/measurements/CHILD_ID',
    'event': 'tedge/events/EVENT_ID/CHILD_ID',
    'alarm': 'tedge/alarms/SEVERITY/TYPE/CHILD_ID'
}


class MappedMessage:
    topic: str = ''
    data: str = ''

    def __init__(self, data, topic):
        self.topic = topic
        self.data = data


class ModbusMapper:
    device = None

    def __init__(self, device):
        self.device = device

    def mapregister(self, registerresponse: ReadRegistersResponseBase, registerdef):
        messages = []
        startbit = registerdef['startbit']
        fieldlength = registerdef['nobits']
        is_little_endian = registerdef.get('littleendian') or False
        is_litte_word_endian = self.device.get('littlewordendian') or False
        readregister = registerresponse.registers
        if fieldlength > 16 and startbit > 0:
            raise Exception('float values must align to the zero bit of the start register')
        if fieldlength > 16:
            value = self.parse_register_value(readregister, self.gettargettype(registerdef),
                                              little_endian=is_little_endian, word_endian=is_litte_word_endian)
        else:
            buffer = self.buffer_register(readregister, is_little_endian, is_litte_word_endian)
            buflength = len(readregister) * 16
            buffer = buffer >> (buflength - (startbit + fieldlength))
            mask = 0xffff
            i = 1
            while i < len(readregister):
                mask = (mask << 16) + 0xffff
                i = i + 1
            mask = mask >> (buflength - fieldlength)
            is_negative = buffer >> (fieldlength - 1) & 0x01
            if registerdef.get('signed') and is_negative:
                value = -(((buffer ^ mask) + 1) & mask)
            else:
                value = buffer & mask
        if registerdef.get('measurementmapping') is not None:
            value = value * (registerdef.get('multiplier') or 1) * (
                    10 ** (registerdef.get('decimalshiftright') or 0)) / (
                            registerdef.get('divisor') or 1)
            data = registerdef['measurementmapping']['templatestring'].replace('%%', str(value))
            messages.append(MappedMessage(data, topics['measurement'].replace('CHILD_ID', self.device.get('name'))))
        return messages

    def mapcoil(self, result: ReadBitsResponseBase, coildefinition):
        messages = []
        if coildefinition.get('alarmmapping') is not None:
            if result.bits[0] > 0:
                severity = coildefinition['alarmmapping']['severity']
                alarmtype = coildefinition['alarmmapping']['type']
                text = coildefinition['alarmmapping']['text']
                # raise alarm if bit is 1
                topic = topics['alarm']
                topic = topic.replace('CHILD_ID', self.device.get('name'))
                topic = topic.replace('SEVERITY', severity)
                topic = topic.replace('TYPE', alarmtype)
                data = {'text': text, 'time': datetime.now(timezone.utc).isoformat()}
                messages.append(MappedMessage(json.dumps(data), topic))
        return messages

    @staticmethod
    def gettargettype(registerdef):
        if registerdef['nobits'] > 32:
            return 'float64'
        elif registerdef['nobits'] > 16:
            return 'float32'
        elif registerdef.get('signed') == False:
            return 'uint16'
        return 'int16'

    @staticmethod
    def parse_register_value(read_registers, target_type, little_endian, word_endian):
        decoder = BinaryPayloadDecoder.fromRegisters(read_registers,
                                                     byteorder=Endian.Little if little_endian else Endian.Big,
                                                     wordorder=Endian.Little if word_endian else Endian.Big)
        return decoder_func[target_type](decoder)

    @staticmethod
    def buffer_register(register: list, litte_endian, is_litte_word_endian):
        buf = 0x0000000000000000

        if is_litte_word_endian:
            for reg in reversed(register):
                buf = (buf << 16) | reg if not litte_endian else (reg >> 8) | (reg << 8)
        else:
            for reg in register:
                buf = (buf << 16) | reg if not litte_endian else (reg >> 8) | (reg << 8)

        return buf
