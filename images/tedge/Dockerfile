#Build dpkg package
FROM debian:stable as dpkg-build-stage

ENV DEBIAN_FRONTEND=noninteractive
# Install build dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    python3 \
    python3-pip \
    python3-venv \
    devscripts \ 
    equivs \
    debhelper \
    dh-virtualenv \
    python3-virtualenv \
    python3-stdeb \
    python3-dev


# Copy required files
WORKDIR /build
COPY modbus_reader /build/modbus_reader
COPY operations /build/operations
COPY debian /build/debian
COPY pyproject.toml /build/pyproject.toml
COPY LICENSE /build/LICENSE
COPY setup.py /build/setup.py
COPY config /build/config
COPY requirements.txt /build/requirements.txt

# Install requiered python packages
RUN python3 -m venv /opt/venv
RUN . /opt/venv/bin/activate && pip install build
RUN . /opt/venv/bin/activate && pip install pyinstaller
RUN . /opt/venv/bin/activate && pip install -r /build/requirements.txt

# Copy and build operations
COPY operations /build/operations
RUN . /opt/venv/bin/activate && exec pyinstaller ./operations/c8y_ModbusConfiguration/c8y_ModbusConfiguration.py --onefile --distpath ./operations/c8y_ModbusConfiguration/dist


# Build python wheel
RUN . /opt/venv/bin/activate && exec python -m build


#Build dpkg package
RUN dpkg-buildpackage -us -uc -b

FROM ghcr.io/thin-edge/tedge-demo-main-systemd:20231105.1
# Install Modbus Plugin
COPY --from=dpkg-build-stage /te-modbus-plugin_0.4.0_all.deb /tmp/te-modbus-plugin_0.4.0_all.deb
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    /tmp/te-modbus-plugin_0.4.0_all.deb \
    && rm /tmp/te-modbus-plugin_0.4.0_all.deb

#Add confguration plugin config
COPY images/tedge/tedge-configuration-plugin.toml /etc/tedge/plugins/tedge-configuration-plugin.toml
COPY images/tedge/tedge-log-plugin.toml /etc/tedge/plugins/tedge-log-plugin.toml
#Add logfile plugin config



#Install Dependencys
# RUN apt-get update \
#     && DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends install \
#     python3 \
#     pip

#Install Python Dependencys
# COPY requirements.txt /tmp/requirements.txt
# RUN pip install -r /tmp/requirements.txt

#Install Modbus Plugin
# COPY /modbus_reader /app

#Add Modbus Fragment
# COPY /images/tedge/inventory.json /etc/tedge/device/inventory.json

# # Add modbus configuration operation plugin
# COPY /operations/c8y_ModbusConfiguration/c8y_ModbusConfiguration /etc/tedge/operations/c8y/c8y_ModbusConfiguration
# COPY /operations/c8y_ModbusConfiguration/c8y_ModbusConfiguration.py /bin/c8y_ModbusConfiguration.py
# RUN chmod 555 /bin/c8y_ModbusConfiguration.py

# Add modbus device operation plugin
# COPY /operations/c8y_ModbusDevice/c8y_ModbusDevice /etc/tedge/operations/c8y/c8y_ModbusDevice
# COPY /operations/c8y_ModbusDevice/c8y_ModbusDevice.py /bin/c8y_ModbusDevice.py
# RUN chmod 555 /bin/c8y_ModbusDevice.py

# Add modbus config and devices to container
# COPY /images/tedge/devices.toml /etc/tedge/plugins/modbus/devices.toml
# COPY /images/tedge/modbus.toml /etc/tedge/plugins/modbus/modbus.toml



