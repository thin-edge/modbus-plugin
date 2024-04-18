#!/usr/bin/env python3
"""Cumulocity IoT c8y_Coils operation handler
"""
from .context import Context


def run(arguments, context: Context):
    """Run c8y_Coils operation handler"""
    config_file = context.config_dir / f"{__name__}.toml"
    context.config_dir.mkdir(parents=True, exist_ok=True)
    with open(config_file, mode="w", newline="", encoding="utf8") as file:
        file.write(arguments)
