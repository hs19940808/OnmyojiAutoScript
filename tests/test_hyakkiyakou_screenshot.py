from collections import deque
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import numpy as np

from module.exception import RequestHumanTakeover
from tasks.Hyakkiyakou.config import ScreenshotMethod
from tasks.Hyakkiyakou.slave.hya_device import HyaDevice


def make_task(window_image=None, window_error=None):
    frame = np.full((720, 1280, 3), 32, dtype=np.uint8)
    task = HyaDevice.__new__(HyaDevice)
    task.config = SimpleNamespace(script=SimpleNamespace(error=SimpleNamespace(save_error=True)))
    task.hya_screenshot_interval = Mock()
    task.hya_fs_check_timer = Mock()
    task.hya_fs_check_timer.reached.return_value = False
    task.device = SimpleNamespace(
        screenshot_window_background=Mock(
            return_value=frame if window_image is None else window_image,
            side_effect=window_error,
        ),
        screenshot_adb_nc=Mock(return_value=frame),
        screenshot_nemu_ipc=Mock(return_value=frame),
        screenshot_deque=deque(),
    )
    return task, frame


class HyakkiyakouScreenshotTests(unittest.TestCase):
    def test_unusable_window_capture_falls_back_once_and_keeps_error_history(self):
        for failure in ['black', 'scaled', 'missing_handle', 'empty_tree']:
            with self.subTest(failure=failure):
                image = {
                    'black': np.zeros((720, 1280, 3), dtype=np.uint8),
                    'scaled': np.ones((782, 1391, 3), dtype=np.uint8),
                }.get(failure)
                error = {'missing_handle': AttributeError('root_node'), 'empty_tree': IndexError()}.get(failure)
                task, frame = make_task(image, error)
                self.assertIs(task.fast_screenshot(ScreenshotMethod.WINDOW_BACKGROUND), frame)
                self.assertIs(task.fast_screenshot(ScreenshotMethod.WINDOW_BACKGROUND), frame)
                task.device.screenshot_window_background.assert_called_once()
                self.assertEqual(task.device.screenshot_adb_nc.call_count, 2)
                self.assertEqual(len(task.device.screenshot_deque), 2)
                self.assertIs(task.device.screenshot_deque[-1]['image'], frame)

    def test_working_window_capture_keeps_fast_backend(self):
        task, frame = make_task()
        self.assertIs(task.fast_screenshot(ScreenshotMethod.WINDOW_BACKGROUND), frame)
        task.device.screenshot_adb_nc.assert_not_called()

    def test_black_adb_fallback_still_requests_takeover(self):
        task, _ = make_task(np.zeros((720, 1280, 3), dtype=np.uint8))
        task.device.screenshot_adb_nc.return_value = np.zeros((720, 1280, 3), dtype=np.uint8)
        with self.assertRaises(RequestHumanTakeover):
            task.fast_screenshot(ScreenshotMethod.WINDOW_BACKGROUND)

    def test_nemu_selection_is_preserved_after_window_fallback(self):
        task, frame = make_task()
        task._hya_use_adb_nc = True
        self.assertIs(task.fast_screenshot(ScreenshotMethod.NEMU_IPC), frame)
        task.device.screenshot_nemu_ipc.assert_called_once()
        task.device.screenshot_adb_nc.assert_not_called()


if __name__ == '__main__':
    unittest.main()
