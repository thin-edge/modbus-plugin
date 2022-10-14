#!/usr/bin/python3
# coding=utf-8
import logging
logger = logging.getLogger('Logger')
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger.info("Logger was initialized")

import pyfiglet
import sys
#from pymodbus.client import ModbusTCPClient
from pyModbusTCP.client import ModbusClient

from watchdog.observers.polling import PollingObserver as Observer
from watchdog.events import LoggingEventHandler



def print_banner():
    logger.info(pyfiglet.figlet_format("Modbus plugin for thin-edge.io"))
    logger.info("Author:\t\tRina,Mario,Murat")
    logger.info("Date:\t\t12th October 2022")
    logger.info("Description:\tA service that extracts data from a Modbus Server and sends it to a local thin-edge.io broker.")
    logger.info("Documentation:\tPlease refer to the c8y-documentation wiki to find service description")

def test():
    client = ModbusClient(host="0.0.0.0",port=502, auto_open=True, auto_close=True, debug=True)
    result = client.read_holding_registers(0, 1)
    logger.debug(result)
        
if __name__== "__main__":
    try:
        logger.info("Starting")
        print_banner()
        test()
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as e:
        logger.error(f'The following error occured: {e}')