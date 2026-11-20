from datetime import datetime, timedelta
import unittest

from oashya.labels import CLASSINDEX as CI
from tasks.Hyakkiyakou.agent.agent import Agent
from tasks.Hyakkiyakou.agent.focus import Focus
from tasks.Hyakkiyakou.slave.hya_slave import HyaBuff


def track(class_id, ident=1, x=900):
    return (ident, class_id, 0.95, x, 450, 100, 150, 0)


class HyakkiyakouStrategyTests(unittest.TestCase):
    def ready_agent(self, strategy=None):
        agent = Agent(strategy)
        agent.last_throw_time = datetime.now() - timedelta(seconds=2)
        return agent

    def test_every_r_card_is_a_valid_target_including_tongnan_and_tongnv(self):
        for class_id in (CI.MIN_R, CI.R_007, CI.R_008, CI.MAX_R):
            with self.subTest(class_id=class_id):
                agent = self.ready_agent()
                action = agent.decision([track(class_id)], [250, 35, 10, -1, -1, -1, -1])
                self.assertTrue(action[2])
                self.assertEqual(agent.focus._class, class_id)

    def test_rare_target_without_probability_buff_no_longer_blocks_all_throws(self):
        for class_id in (CI.MIN_SSR, CI.MIN_SP):
            with self.subTest(class_id=class_id):
                agent = self.ready_agent()
                tracks = [track(class_id), track(CI.MIN_SR, ident=2, x=400)]
                self.assertTrue(agent.decision(tracks, [250, 30, 10, -1, -1, -1, -1])[2])

    def test_remaining_beans_are_spent_near_the_end(self):
        self.assertGreater(Focus.r([1000, 10, 1, 10], omega=0.7, omega_buff=0), 0)

    def test_n_cards_are_attacked_even_with_a_legacy_zero_weight(self):
        agent = self.ready_agent({'weights': [0, 0, 0, 0, 0, 0]})
        action = agent.decision([track(CI.MIN_N)], [250, 35, 5, -1, -1, -1, -1])
        self.assertTrue(action[2])
        self.assertEqual(action[3], 5)

    def test_empty_beans_block_but_freeze_does_not_block_a_visible_target(self):
        self.assertLess(Focus.r([1000, 0, 10, 10], 1, 0), 0)
        agent = self.ready_agent()
        self.assertTrue(agent.decision([track(CI.MIN_R)], [200, 20, 5, -1, -1, -1, -1], freeze=True)[2])

    def test_strict_rarity_order_ignores_position_and_lower_rarity_density(self):
        classes = [CI.MIN_SP, CI.MIN_SSR, CI.MIN_SR, CI.MIN_R, CI.MIN_N]
        for higher, lower in zip(classes, classes[1:]):
            with self.subTest(higher=higher, lower=lower):
                agent = self.ready_agent()
                tracks = [track(higher, x=80)] + [track(lower, ident=i+2, x=900+i) for i in range(6)]
                self.assertTrue(agent.decision(tracks, [250, 35, 5, -1, -1, -1, -1])[2])
                self.assertEqual(agent.focus._class, higher)

    def test_probability_buff_does_not_replace_a_visible_sp_target(self):
        agent = self.ready_agent()
        action = agent.decision([track(CI.MIN_SP), track(CI.BUFF_006, ident=2, x=300)],
                                [250, 35, 5, -1, -1, -1, -1])
        self.assertTrue(action[2])
        self.assertEqual(action[:2], [850, 410])
        self.assertEqual(action[3], 5)

    def test_buff_only_frame_does_not_throw_at_a_non_shikigami(self):
        agent = self.ready_agent()
        self.assertFalse(agent.decision([track(CI.BUFF_006)], [250, 35, 5, -1, -1, -1, -1])[2])

    def test_cooldown_and_acceleration_buff(self):
        self.assertLess(Focus.r([100, 250, 35, 10], 1, 0), 0)
        self.assertGreater(Focus.r([250, 250, 35, 10], 1, 0), 0)
        self.assertLess(Focus.r([200, 250, 35, 10, HyaBuff.BUFF_STATE0], 1, 0), 0)
        self.assertGreater(Focus.r([200, 250, 35, 10, HyaBuff.BUFF_STATE3], 1, 0), 0)


if __name__ == '__main__':
    unittest.main()
