from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from module.exception import RequestHumanTakeover
from tasks.Hyakkiyakou.slave.hya_slave import HyaSlave


class HyakkiyakouBeansTests(unittest.TestCase):
    def make_task(self):
        task = HyaSlave.__new__(HyaSlave)
        task.bean_10to05 = Mock()
        task.screenshot = Mock()
        return task

    def test_existing_five_beans_does_not_move_the_slider(self):
        task = self.make_task()
        task.recognize_bean_05 = Mock(return_value=True)
        task.ensure_bean_05()
        task.bean_10to05.assert_not_called()

    def test_ten_beans_switches_to_five_and_verifies_a_new_frame(self):
        task = self.make_task()
        task.recognize_bean_05 = Mock(side_effect=[False, True])
        task.ensure_bean_05()
        task.bean_10to05.assert_called_once()
        task.screenshot.assert_called_once()

    def test_unverified_slider_stops_instead_of_throwing_ten_beans(self):
        task = self.make_task()
        task.recognize_bean_05 = Mock(return_value=False)
        with self.assertRaises(RequestHumanTakeover):
            task.ensure_bean_05()
        self.assertEqual(task.bean_10to05.call_count, 3)

    def test_five_bean_deductions_and_hundreds_unit_are_read_correctly(self):
        for previous, actual in [(250, 245), (245, 240), (105, 100), (100, 95), (10, 5), (5, 0)]:
            with self.subTest(previous=previous, actual=actual):
                task = self.make_task()
                task.__dict__['bean'] = [SimpleNamespace(digit=i, roi_back=None) for i in range(10)]
                task.device = SimpleNamespace(image=None)
                task.O_BEAN_NUMBER = SimpleNamespace(ocr=Mock(return_value=actual))
                if actual >= 100:
                    digits = {tuple(task.HUNDRED0HUNDRED): actual // 100,
                              tuple(task.DECADE0HUNDRED): actual // 10 % 10,
                              tuple(task.UNIT0HUNDRED): actual % 10}
                elif actual >= 10:
                    digits = {tuple(task.DECADE0DECADE): actual // 10,
                              tuple(task.UNIT0DECADE): actual % 10}
                else:
                    digits = {tuple(task.UNIT0): actual}
                task.appear = lambda img: digits.get(tuple(img.roi_back)) == img.digit
                self.assertEqual(task.predict_bean(previous), actual)
                task.O_BEAN_NUMBER.ocr.assert_not_called()


if __name__ == '__main__':
    unittest.main()
