import os.path

from pkg_resources import parse_requirements
from setuptools import setup, find_packages

setup(
    name='te-modbus-reader',
    version='0.1',
    description='Modbus plugin for thin-edge',
    url='https://github.com/thin-edge/modbus-plugin',
    author='Software AG ♥ thin-edge.io',
    author_email='info@thin-edge.io',
    license='MIT',
    install_requires=[
        'paho-mqtt~=1.6.1',
        'pymodbus==3.0.0',
        'watchdog',
        'pyfiglet',
        'tomli~=2.0.1',
        'pyserial-asyncio'],
    packages=find_packages(),
    data_files=[('config/devices.toml', ['config/devices.toml']), ('config/modbus.toml', ['config/modbus.toml'])],
    entry_points=dict(
        console_scripts=['te-modbus-reader=modbus_reader.reader:main']
    )
)
