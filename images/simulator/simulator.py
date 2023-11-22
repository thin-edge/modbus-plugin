# See also example https://pymodbus.readthedocs.io/en/latest/source/example/updating_server.html
import logging
import asyncio
from threading import Thread
from pymodbus.server import ModbusSimulatorServer

logger = logging.getLogger('Modbus Server')
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


async def run_server():
    """Combine setup and run"""
    await ModbusSimulatorServer(modbus_server="server", modbus_device="device", json_file='modbus.json').run_forever()

if __name__ == "__main__":
    asyncio.run(run_server(), debug=True)

   

    
    