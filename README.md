# modbus-plugin

# Requirements
* Python >= 3.9

# Setup (without deb package)
* copy modbus-plugin folder to target device
* ssh into device and go to the plugin folder
* create the virtualenv with `python -m venv venv`
* activate venv environment with `source ./venv/bin/activate`
* install all dependencies with `python -m pip install -r requirements.txt`
* run the reader with `python c8y_ModbusListener/reader.py -c ./config`

# Config files

All config files are expected to be in the /etc/tedge/plugins/modbus folder. 
As alternative the directory can be based with -c or --configdir to the python script like so:
`python c8y_ModbusListener/reader.py --configdir <configfolder>`


## modbus.toml
Includes the basic configuration for the plugin: 
* poll rate
* connection to thin-edge (MQTT broker needs to match the one of tedge)

## devices.toml

Defines the existing child devices and their protocol for polling the Modbus folder.
The structure is based on the Cloud Fieldbus protocols.

## watchdog
The watchdog will take care of restarting the MQTT and Modbus connection when either
devices.toml or modbus.toml changes. So there should be no need to manually restart the 
python script.