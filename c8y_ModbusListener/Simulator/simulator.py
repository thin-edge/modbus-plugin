# See also example https://pymodbus.readthedocs.io/en/latest/source/example/updating_server.html
import logging
from threading import Thread
from pymodbus.constants import Endian
from pymodbus.server import StartTcpServer as StartServer
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from pymodbus.payload import BinaryPayloadBuilder

import time
import math


def updating_writer(a):
    while True:        
        logger.info('updating context')
        seconds = time.time()
        frequency = 100
        amplitude = 5
        simPower = amplitude*math.sin(seconds*frequency/100)
        logger.info('Power is ' + str(simPower))
        builder = BinaryPayloadBuilder(byteorder=Endian.Little)
        builder.add_16bit_int(int(simPower*1000))
        payload = builder.to_registers()        
        logger.info('Payload is ' + ''.join(str(p) for p in payload))
        logger.info('Updating context')
        register = 3
        slave_id = 0
        address = 0
        logger.info("new values: " + str(payload))
        context[slave_id].setValues(register, address, payload)
        time.sleep(30)
    
if __name__ == "__main__":
    logger = logging.getLogger('Modbus Server')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info('Logger for Modbus Server was initialised')
    builder  = BinaryPayloadBuilder()  
    store = ModbusSlaveContext()
    context = ModbusServerContext(slaves=store, single=True)
    #Start updating thread
    logger.info('Starting writer')
    writer = Thread(target=updating_writer, args=(context,))
    writer.start()
    #Start Modbus Server
    logger.info('Starting Modbus Server')
    StartServer(context=context, address=("0.0.0.0", 502))
    
    