from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from tasks.Hyakkiyakou.config import ScreenshotMethod
from tasks.Hyakkiyakou.script_task import ScriptTask


class HyakkiyakouLoopTests(unittest.TestCase):
    def test_frozen_frame_still_reaches_detection_decision_and_throw(self):
        task = ScriptTask.__new__(ScriptTask)
        debug = SimpleNamespace(hya_show=False, hya_save_result=False, continuous_learning=False,
                                hya_info=False, hya_screenshot_method=ScreenshotMethod.WINDOW_BACKGROUND)
        task.config = SimpleNamespace(hyakkiyakou=SimpleNamespace(
            debug_config=debug, hyakkiyakou_config=SimpleNamespace(hya_invite_friend=False)))
        frame = object()
        state = [250, 35, 5, -1, -1, -1, -1]
        tracks = [(1, 36, 0.9, 900, 450, 100, 150, 0)]
        action = [850, 410, True, 5]
        task.device = SimpleNamespace(image=frame, stuck_record_add=Mock())
        task.slave_state = state
        task.hya_fs_check_timer = Mock()
        for method in ('reset_state', 'ui_click', 'wait_until_appear', '_select_best_boss',
                       'screenshot', 'fast_screenshot', 'ensure_bean_05', 'do_action'):
            setattr(task, method, Mock())
        task.update_state = Mock(return_value=state)
        task.__dict__['tracker'] = Mock(return_value=tracks)
        task.__dict__['agent'] = SimpleNamespace(decision=Mock(return_value=action))
        task.__dict__['debugger'] = Mock()
        end_frames = iter([False, False, True])

        def appear(asset):
            if asset is task.I_HEND:
                return next(end_frames)
            if asset is task.I_HTITLE:
                return False
            return True

        task.appear = appear
        task.one()

        task.ensure_bean_05.assert_called_once()
        task.tracker.assert_called_once_with(image=frame, response=[0, 0, False, 5])
        task.agent.decision.assert_called_once_with(tracks=tracks, state=state, freeze=True)
        task.do_action.assert_called_once_with(action, state=state)


if __name__ == '__main__':
    unittest.main()
