"""thin-edge.io Modbus operations handlers"""

import sys

from . import c8y_coils
from . import c8y_modbus_configuration
from . import c8y_modbus_device
from . import c8y_registers
from . import c8y_serial_configuration
from .context import Context


def main():
    """main"""
    command = sys.argv[1]
    if command == "c8y_Coils":
        run = c8y_coils.run
    elif command == "c8y_ModbusConfiguration":
        run = c8y_modbus_configuration.run
    elif command == "c8y_ModbusDevice":
        run = c8y_modbus_device.run
    elif command == "c8y_Registers":
        run = c8y_registers.run
    elif command == "c8y_SerialConfiguration":
        run = c8y_serial_configuration.run

    arguments = sys.argv[2:]
    context = Context()
    run(arguments, context)


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        print(f"Error: {ex}", file=sys.stderr)
        sys.exit(1)
