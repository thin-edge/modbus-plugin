"""Operation context"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
import toml


@dataclass
class Context:
    """Operation context to provide access to common settings"""

    # TODO: Get broker and port from thin-edge options
    broker = "localhost"
    port = 1883
    client_id = "c8y_ModbusConfiguration-operation-client"
    config_dir = Path("/etc/tedge/plugins/modbus")
    base_config_path = config_dir / "modbus.toml"

    @property
    def c8y_proxy(self) -> str:
        """Cumulocity IoT c8y proxy service"""
        return f"http://{self.broker}:8001/c8y"

    @property
    def device_id(self):
        """Get thin-edge.io device id"""
        try:
            # Run the command and capture the output
            result = subprocess.run(
                ["tedge", "config", "get", "device.id"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as proc_err:
            raise proc_err

    @property
    def base_config(self):
        """loads the default modbus.toml file and gives it back as dict"""
        return toml.load(self.base_config_path)
