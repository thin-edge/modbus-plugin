import unittest
import struct
import os
import sys

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, parent_dir)
from tedge_modbus.reader.mapper import ModbusMapper

import unittest
import struct
import json
from tedge_modbus.reader.mapper import ModbusMapper


class TestMapperOnChange(unittest.TestCase):
    def setUp(self):
        """Set up a new ModbusMapper instance for each test."""
        self.mock_device = {
            "name": "test_device",
            "littlewordendian": False,
        }
        self.mapper = ModbusMapper(self.mock_device)

    def test_on_change_true_and_value_changes(self):
        register_def = {
            "number": 100,
            "startbit": 0,
            "nobits": 16,
            "signed": False,
            "on_change": True,
            "measurementmapping": {"templatestring": '{"temp": %%}'},
        }

        # First poll: Should always publish
        messages1 = self.mapper.map_register(
            read_register=[123], register_def=register_def
        )
        self.assertEqual(len(messages1), 1, "Should publish on first poll")
        data1 = json.loads(messages1[0].data)
        self.assertAlmostEqual(data1["temp"], 123.0)

        # Second poll with a different value: Should publish
        messages2 = self.mapper.map_register(
            read_register=[456], register_def=register_def
        )
        self.assertEqual(len(messages2), 1, "Should publish when value changes")
        data2 = json.loads(messages2[0].data)
        self.assertAlmostEqual(data2["temp"], 456.0)

    def test_on_change_true_and_value_is_same(self):
        register_def = {
            "number": 100,
            "startbit": 0,
            "nobits": 16,
            "signed": False,
            "on_change": True,
            "measurementmapping": {"templatestring": '{"temp": %%}'},
        }

        # First poll: should publish
        messages1 = self.mapper.map_register(
            read_register=[123], register_def=register_def
        )
        self.assertEqual(len(messages1), 1, "Should publish on first poll")

        # Second poll with the same value: should NOT publish
        messages2 = self.mapper.map_register(
            read_register=[123], register_def=register_def
        )
        self.assertEqual(
            len(messages2), 0, "Should not publish when value is unchanged"
        )

    def test_on_change_false_and_value_is_same(self):
        register_def = {
            "number": 100,
            "startbit": 0,
            "nobits": 16,
            "signed": False,
            "on_change": False,
            "measurementmapping": {"templatestring": '{"temp": %%}'},
        }

        messages1 = self.mapper.map_register(
            read_register=[123], register_def=register_def
        )
        self.assertEqual(len(messages1), 1)

        messages2 = self.mapper.map_register(
            read_register=[123], register_def=register_def
        )
        self.assertEqual(
            len(messages2), 1, "Should always publish when on_change is false"
        )

    def test_on_change_not_present_and_value_is_same(self):
        register_def = {
            "number": 100,
            "startbit": 0,
            "nobits": 16,
            "signed": False,
            "measurementmapping": {"templatestring": '{"temp": %%}'},
        }

        messages1 = self.mapper.map_register(
            read_register=[123], register_def=register_def
        )
        self.assertEqual(len(messages1), 1)

        messages2 = self.mapper.map_register(
            read_register=[123], register_def=register_def
        )
        self.assertEqual(
            len(messages2), 1, "Should default to on_change=false and always publish"
        )

    def test_on_change_with_float_values(self):
        def float_to_regs(f_val):
            packed = struct.pack(">f", f_val)
            return struct.unpack(">HH", packed)

        register_def = {
            "number": 102,
            "startbit": 0,
            "nobits": 32,
            "signed": True,
            "on_change": True,
            "datatype": "float",
            "measurementmapping": {"templatestring": '{"voltage": %%}'},
        }

        # First poll with 123.45
        messages1 = self.mapper.map_register(
            read_register=list(float_to_regs(123.45)), register_def=register_def
        )
        self.assertEqual(
            len(messages1), 1, "Should publish on first poll for float value"
        )
        data1 = json.loads(messages1[0].data)
        self.assertAlmostEqual(data1["voltage"], 123.45, places=5)

        # Second poll, same value
        messages2 = self.mapper.map_register(
            read_register=list(float_to_regs(123.45)), register_def=register_def
        )
        self.assertEqual(
            len(messages2), 0, "Should not publish when float value is the same"
        )

        # Third poll, very close value (should be considered the same by math.isclose)
        close_value = 123.45 + 1e-8
        messages3 = self.mapper.map_register(
            read_register=list(float_to_regs(close_value)), register_def=register_def
        )
        self.assertEqual(
            len(messages3), 0, "Should not publish for very close float values"
        )

        # Fourth poll, different value
        messages4 = self.mapper.map_register(
            read_register=list(float_to_regs(125.0)), register_def=register_def
        )
        self.assertEqual(
            len(messages4), 1, "Should publish when float value changes significantly"
        )
        data4 = json.loads(messages4[0].data)
        self.assertAlmostEqual(data4["voltage"], 125.0)
