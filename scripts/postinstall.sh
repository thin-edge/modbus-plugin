#!/bin/sh

set -e

# Set paths
MODBUS_PLUGINS_PATH="/etc/tedge/plugins/modbus"
PYTHON_VENV_PATH="/etc/tedge/plugins/modbus/venv"
LOG_PATH="/var/log/te-modbus-plugin/modbus.log"
# System D paths
SYSTEMD_PATH="/lib/systemd/system"
SYSTEMD_SERVICE="te-modbus-plugin.service"

# Create python venv and install requirements
python3 -m venv "$PYTHON_VENV_PATH"
"$PYTHON_VENV_PATH/bin/pip3" install -r "$MODBUS_PLUGINS_PATH/requirements.txt"

# Enable SmartRest Templates modbus on tedge
tedge config set c8y.smartrest.templates modbus

# Enable system d only if systemctl is available
if command -v systemctl >/dev/null; then
        # Create service file
        touch "$SYSTEMD_PATH/$SYSTEMD_SERVICE"
        echo "[Unit]" >> "$SYSTEMD_PATH/$SYSTEMD_SERVICE"
        echo "Description=Modbus Reader" >> "$SYSTEMD_PATH/$SYSTEMD_SERVICE"
        echo "" >> "$SYSTEMD_PATH/$SYSTEMD_SERVICE"
        echo "[Service]" >> "$SYSTEMD_PATH/$SYSTEMD_SERVICE"
        echo "User=root" >> "$SYSTEMD_PATH/$SYSTEMD_SERVICE"
        echo "Restart=on-failure" >> "$SYSTEMD_PATH/$SYSTEMD_SERVICE"
        echo "ExecStart=$PYTHON_VENV_PATH/bin/python3 $MODBUS_PLUGINS_PATH/modbus_reader/reader.py -l $LOG_PATH" >> "$SYSTEMD_PATH/$SYSTEMD_SERVICE"
        echo "" >> "$SYSTEMD_PATH/$SYSTEMD_SERVICE"
        echo "[Install]" >> "$SYSTEMD_PATH/$SYSTEMD_SERVICE"
        echo "WantedBy=multi-user.target" >> "$SYSTEMD_PATH/$SYSTEMD_SERVICE"

        # Enable System D Service
        systemctl enable te-modbus-plugin.service
fi
