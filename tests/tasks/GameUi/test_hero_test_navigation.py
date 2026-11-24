"""Regression coverage for the loading screen before Hero Test."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tasks.GameUi.default_pages import page_exploration, page_hero_test
from tasks.GameUi.navigator import GameUi
from tasks.GameUi.session import NavigatorSession


class HeroTestNavigationTests(unittest.TestCase):
    def test_waits_for_the_trial_page_after_an_eight_second_load(self):
        """The session edge waits for the loaded page after a single click."""
        session = NavigatorSession(task_category="hero_test")
        session.bootstrap([page_exploration, page_hero_test])
        exploration = session.resolve_page(page_exploration)
        hero_test = session.resolve_page(page_hero_test)
        transition = next(
            edge for edge in exploration.transitions if edge.destination == hero_test
        )
        task = Mock(spec=GameUi)
        task.navigator = session
        task._execute_action.return_value = True
        task._wait_for_destination = GameUi._wait_for_destination.__get__(task)
        elapsed = 1.0

        def confirm_page(page, *, skip_first_screenshot):
            """Advance the clock while the simulated loading screen is visible."""
            nonlocal elapsed
            elapsed += 1
            return page == hero_test and elapsed >= 9

        task.confirm_page.side_effect = confirm_page
        clock = SimpleNamespace(time=lambda: elapsed)
        with patch("module.base.timer.time", clock):
            self.assertTrue(GameUi._execute_transition(task, transition))

        task._execute_action.assert_called_once()
        task._detect_current_page_with_fallback.assert_not_called()
        self.assertIs(session.current_page, hero_test)
        self.assertEqual(session.penalty_of(transition), 0.0)
