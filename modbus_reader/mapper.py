import json

from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.bit_read_message import ReadBitsResponseBase
from pymodbus.register_read_message import ReadRegistersResponseBase
from datetime import datetime, timezone

decoder_func = {
    'int16': lambda d: d.decode_16bit_int(),
    'uint16': lambda d: d.decode_16bit_uint(),
    'int32': lambda d: d.decode_32bit_int(),
    'uint32': lambda d: d.decode_32bit_uint(),
    'int64': lambda d: d.decode_64bit_int(),
    'uint64': lambda d: d.decode_64bit_uint(),
    'float32': lambda d: d.decode_32bit_float(),
    'float64': lambda d: d.decode_64bit_float()
}

topics = {
    'measurement': 'tedge/measurements/CHILD_ID',
    'event': 'tedge/events/TYPE/CHILD_ID',
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

    # store data to be able to compare them later
    data = {'hr': {}, 'ir': {}, 'co': {}, 'di': {}}

    def __init__(self, device):
        self.device = device

    def mapregister(self, registerresponse: ReadRegistersResponseBase, registerdef):
        messages = []
        startbit = registerdef['startbit']
        fieldlength = registerdef['nobits']
        is_little_endian = registerdef.get('littleendian') or False
        is_litte_word_endian = self.device.get('littlewordendian') or False
        readregister = registerresponse.registers
        registertype = 'ir' if (registerdef.get('input') or False) else 'hr'
        registerkey = f'{registerdef["number"]}:{registerdef["startbit"]}'
        if fieldlength > 16 and startbit > 0:
            raise Exception('values spanning registers must align to the zero bit of the start register')
        if fieldlength > 16:
            value = self.parse_register_value(readregister, self.gettargettype(registerdef),
                                              little_endian=is_little_endian, word_endian=is_litte_word_endian)
        else:
            # concat the registers in case we need to read across multiple registers
            buffer = self.buffer_register(readregister, is_little_endian, is_litte_word_endian)
            buflength = len(readregister) * 16
            # shift and mask for the cases where the startbit > 0 and we are not reading the whole register as value
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
        if registerdef.get('alarmmapping') is not None:
            messages.extend(self.checkalarm(value, registerdef.get('alarmmapping'), registertype, registerkey))
        if registerdef.get('eventmapping') is not None:
            messages.extend(self.checkevent(value, registerdef.get('eventmapping'), registertype, registerkey))
        self.data[registertype][registerkey] = value
        return messages

    def mapcoil(self, result: ReadBitsResponseBase, coildefinition):
        messages = []
        registertype = 'di' if (coildefinition.get('input') or False) else 'co'
        registerkey = coildefinition["number"]
        value = 1 if result.bits[0] else 0
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
    def gettargettype(registerdef):
        dtype = 'int' if registerdef.get('datatype') == 'int' else 'float'
        signed = 'u' if dtype == 'int' and registerdef.get('signed') == False else ''
        length = 16
        if registerdef['nobits'] > 32:
            length = 64
        elif registerdef['nobits'] > 16:
            length = 32
        return f'{signed}{dtype}{length}'

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
