from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from module.device.method.minitouch import Minitouch
from tasks.Hyakkiyakou.config import ControlMethod
from tasks.Hyakkiyakou.slave.hya_device import HyaDevice


class HyakkiyakouMinitouchTests(unittest.TestCase):
    def make_device(self):
        builder = Mock()
        for method in ('down', 'commit', 'wait', 'move', 'up'):
            getattr(builder, method).return_value = builder
        return SimpleNamespace(
            minitouch_builder=builder,
            _humanized_pressure=Mock(return_value=50),
            _humanized_dwell=Mock(return_value=99),
            minitouch_send=Mock(),
        )

    def test_fast_tap_uses_short_dwell_and_releases_contact(self):
        device = self.make_device()
        Minitouch.click_minitouch(device, 500, 400, fast=True)
        duration = device.minitouch_builder.wait.call_args.args[0]
        self.assertGreaterEqual(duration, 20)
        self.assertLessEqual(duration, 35)
        device.minitouch_builder.move.assert_not_called()
        device.minitouch_builder.up.assert_called_once()
        device._humanized_dwell.assert_not_called()
        device.minitouch_send.assert_called_once()

    def test_normal_tap_keeps_existing_dwell_and_motion(self):
        device = self.make_device()
        Minitouch.click_minitouch(device, 500, 400)
        self.assertEqual(device.minitouch_builder.wait.call_args_list[0].args[0], 99)
        device.minitouch_builder.move.assert_called_once()
        device.minitouch_builder.up.assert_called_once()
        device._humanized_dwell.assert_called_once()

    def test_only_hyakkiyakou_fast_click_requests_fast_mode(self):
        task = HyaDevice.__new__(HyaDevice)
        task.device = SimpleNamespace(click_minitouch=Mock())
        task.fast_click(500, 400, ControlMethod.MINITOUCH)
        task.device.click_minitouch.assert_called_once_with(x=500, y=400, fast=True)


if __name__ == '__main__':
    unittest.main()
