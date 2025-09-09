"""Cumulocity IoT SmartREST template definitions"""

# pylint: disable=line-too-long
SMARTREST_TEMPLATES = [
    "11,1,,c8y_ModbusConfiguration,c8y_ModbusConfiguration.transmitRate,c8y_ModbusConfiguration.pollingRate",
    "11,2,,c8y_ModbusDevice,c8y_ModbusDevice.protocol,c8y_ModbusDevice.address,c8y_ModbusDevice.name,c8y_ModbusDevice.ipAddress,c8y_ModbusDevice.id,c8y_ModbusDevice.type",
    "11,3,,c8y_SerialConfiguration,c8y_SerialConfiguration.baudRate,c8y_SerialConfiguration.stopBits,c8y_SerialConfiguration.parity,c8y_SerialConfiguration.dataBits",
]
