"""Exercise HeroTest battle entry with a simulated clock and screens."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tasks.HeroTest.script_task import ScriptTask


class HeroTestBattleEntryTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.last_click = 0.0
        self.challenge_clicks = 0
        self.task = Mock(spec=ScriptTask)
        self.task.device = Mock()
        self.task.success = True
        self.task.screenshot.side_effect = self.advance_frame
        self.task.is_in_battle.return_value = False
        self.task.is_in_prepare.return_value = False
        self.task.appear.return_value = False
        self.task.appear_then_click.side_effect = self.click_visible_challenge

    def advance_frame(self):
        """Advance the simulated clock by one screenshot."""
        self.now += 0.5
        if self.now > 130:
            self.fail('Battle entry did not stop after its timeout')

    def click_visible_challenge(self, button, *, interval):
        """Model the challenge button staying visible during retries."""
        if button is not self.task.O_FIRE or self.now - self.last_click < interval:
            return False
        self.last_click = self.now
        self.challenge_clicks += 1
        return True

    def enter_battle(self):
        """Run the real entry loop with the minimum click limit."""
        clock = SimpleNamespace(time=lambda: self.now)
        with patch('module.base.timer.time', clock), \
                patch('tasks.HeroTest.script_task.random.randint', return_value=3):
            return ScriptTask.enter_battle(self.task)

    def test_accepts_a_battle_that_loads_after_the_last_click(self):
        """A slow battle must still be picked up by HeroTest."""
        self.task.is_in_battle.side_effect = lambda _: self.now >= 112.0
        self.assertTrue(self.enter_battle())
        self.assertEqual(self.challenge_clicks, 3)
        self.assertTrue(self.task.success)

    def test_accepts_a_prepare_screen_before_the_battle_starts(self):
        """The battle can be ready for the configured team setup first."""
        self.task.is_in_prepare.side_effect = lambda _: self.now >= 112.0
        self.assertTrue(self.enter_battle())
        self.assertEqual(self.challenge_clicks, 3)

    def test_stops_after_the_wait_if_no_battle_ever_loads(self):
        """The final wait keeps the click limit and stops after the deadline."""
        self.assertFalse(self.enter_battle())
        self.assertEqual(self.challenge_clicks, 3)
        self.assertGreaterEqual(self.now - self.last_click, 12)
        self.assertFalse(self.task.success)

    def test_ticket_warning_can_end_the_final_wait(self):
        """An explicit ticket warning retains its normal completion status."""
        self.task.appear.side_effect = lambda *_args, **_kwargs: self.now >= 104.0
        self.assertFalse(self.enter_battle())
        self.assertEqual(self.challenge_clicks, 3)
        self.assertTrue(self.task.success)
