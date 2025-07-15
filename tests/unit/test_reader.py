import os
import sys

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, parent_dir)
import unittest
from unittest.mock import patch, MagicMock
from tedge_modbus.reader.reader import ModbusPoll


class TestReaderPollingInterval(unittest.TestCase):

    @patch("tedge_modbus.reader.reader.ModbusPoll.read_base_definition")
    @patch("tedge_modbus.reader.reader.ModbusPoll.read_device_definition")
    def setUp(self, mock_read_device, mock_read_base):
        """Set up a ModbusPoll instance with mocked file reading."""
        # Mock config to prevent errors during initialization
        mock_read_base.return_value = {"thinedge": {}, "modbus": {}}
        mock_read_device.return_value = {}

        self.poll = ModbusPoll(config_dir="/tmp/mock_config")
        # Replace the real scheduler with a mock object for testing
        self.poll.poll_scheduler = MagicMock()

    def test_uses_device_specific_poll_interval(self):
        """
        GIVEN a device has a specific poll_interval
        WHEN the poller schedules the next poll for that device
        THEN it should use the device's interval.
        """
        # GIVEN a global poll interval
        self.poll.base_config = {"modbus": {"pollinterval": 5}}
        # AND a device with its own poll_interval
        device_config = {
            "name": "fast_poller",
            "poll_interval": 1,  # This should be used
        }

        mock_poll_model = MagicMock()
        mock_mapper = MagicMock()

        # WHEN poll_device is called
        # We patch get_data_from_device to avoid real network calls
        with patch.object(
            self.poll,
            "get_data_from_device",
            return_value=(None, None, None, None, None),
        ):
            self.poll.poll_device(device_config, mock_poll_model, mock_mapper)

        # THEN the scheduler should be called with the device's interval
        self.poll.poll_scheduler.enter.assert_called_once()
        call_args, _ = self.poll.poll_scheduler.enter.call_args
        # The first argument to enter() is the delay
        self.assertEqual(call_args[0], 1)

    def test_uses_global_poll_interval_as_fallback(self):
        """
        GIVEN a device does NOT have a specific poll_interval
        WHEN the poller schedules the next poll for that device
        THEN it should use the global pollinterval.
        """
        # GIVEN a global poll interval
        self.poll.base_config = {"modbus": {"pollinterval": 5}}  # This should be used
        # AND a device without its own poll_interval
        device_config = {"name": "normal_poller"}

        mock_poll_model = MagicMock()
        mock_mapper = MagicMock()

        # WHEN poll_device is called
        with patch.object(
            self.poll,
            "get_data_from_device",
            return_value=(None, None, None, None, None),
        ):
            self.poll.poll_device(device_config, mock_poll_model, mock_mapper)

        # THEN the scheduler should be called with the global interval
        self.poll.poll_scheduler.enter.assert_called_once()
        call_args, _ = self.poll.poll_scheduler.enter.call_args
        self.assertEqual(call_args[0], 5)
