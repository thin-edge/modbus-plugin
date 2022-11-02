from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.register_read_message import ReadHoldingRegistersResponse

decoder_func = {
    'int16': lambda d: d.decode_16bit_int(),
    'uint16': lambda d: d.decode_16bit_uint(),
    'float32': lambda d: d.decode_32bit_float(),
    'float64': lambda d: d.decode_64bit_float()
}


class MappedMessage:
    type: str = 'event'
    data: str = ''

    def __init__(self, data, typ='event'):
        self.type = typ
        self.data = data


class ModbusMapper:
    device = None

    def __init__(self, device):
        self.device = device

    def mapregister(self, registerresponse: ReadHoldingRegistersResponse, registerdef):

        outtype = registerdef['type']
        startbit = registerdef['startbit']
        fieldlength = registerdef['nobits']
        is_little_endian = registerdef.get('littleendian') or False
        is_litte_word_endian = self.device.get('littlewordendian') or False
        data = None
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
        if outtype == 'measurement':
            value = value * (registerdef.get('multiplier') or 1) * (
                        10 ** (registerdef.get('decimalshiftright') or 0)) / (
                            registerdef.get('divisor') or 1)
            data = registerdef['templatestring'].replace('%%', str(value))

        return MappedMessage(data, outtype)

    def mapcoil(self, value):
        data = {
            "temperature": value
        }
        return MappedMessage(data, 'measurement')

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
