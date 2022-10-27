class MappedMessage:
    type = 'event'
    data = {}

    def __init__(self, data, typ='event'):
        self.type = typ
        self.data = data


class ModbusMapper:
    protocolmap = {}

    def __init__(self, mappings):
        self.protocolmap = mappings

    def mapregister(self, value):
        data = {
            "temperature": value
        }
        return MappedMessage(data, 'measurement')

    def mapcoil(self, value):
        data = {
            "temperature": value
        }
        return MappedMessage(data, 'measurement')