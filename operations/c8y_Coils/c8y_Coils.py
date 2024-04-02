#!/usr/bin/env python3
import sys
from pathlib import Path

try:
    fileDir = Path("/etc/tedge/plugins/modbus")
    configFile = fileDir / f'{__name__}.toml'
    fileDir.mkdir(parents=True, exist_ok=True)

    array = sys.argv[1].split(',')
    with open(configFile, mode='w', newline='') as file:
        file.write(array)
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
