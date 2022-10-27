from pymodbus.register_read_message import ReadHoldingRegistersResponse
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder


class MappedMessage:
    type: str = 'event'
    data: str = ''

    def __init__(self, data, typ='event'):
        self.type = typ
        self.data = data


class ModbusMapper:
    protocolmap = {}

    def __init__(self, mappings):
        self.protocolmap = mappings

    def maphrregister(self, registerresponse: ReadHoldingRegistersResponse, registerdef):
        outtype = registerdef['type'] or 'measurement'
        startbit = registerdef['startbit']
        fieldlength = registerdef['nobits']
        registerlength = 16
        data = None
        readregister = registerresponse.registers[0]  # support only one register per value for now

        value = readregister >> (registerlength - (startbit + fieldlength)) & (0xffff >> (registerlength - fieldlength))
        if outtype == 'measurement':
            value = value * (registerdef.get('multiplier') or 1) * (registerdef.get('decimalshiftright') or 0) / (
                        registerdef.get('divisor') or 1)
            data = registerdef['templatestring'].replace('%%', str(value))
        elif outtype == 'event':
            value = value * (registerdef['multiplier'] or 1)
            data = registerdef['templatestring'].replace('%%', str(value))
        elif outtype == 'alarm':
            value = value * (registerdef['multiplier'] or 1)
            data = registerdef['templatestring'].replace('%%', str(value))
        return MappedMessage(data, outtype)

    def mapcoil(self, value):
        data = {
            "temperature": value
        }
        return MappedMessage(data, 'measurement')
