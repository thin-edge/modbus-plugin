import os.path

from pkg_resources import parse_requirements
from setuptools import setup, find_packages

setup(
    name='te-modbus-reader',
    version='0.1',
    description='Modbus plugin for ',
    url='http://github.com/trstringer/python3-random-quote',
    author='Software AG ♥ thin-edge.io',
    author_email='github@trstringer.com',
    license='MIT',
    install_requires=[
        'paho-mqtt~=1.6.1',
        'pymodbus==3.0.0',
        'watchdog',
        'pyfiglet',
        'tomli~=2.0.1',
        'pyserial-asyncio'],
    packages=find_packages(),
    entry_points=dict(
        console_scripts=['te-modbus-reader=modbus_reader.reader:main']
    )
)
