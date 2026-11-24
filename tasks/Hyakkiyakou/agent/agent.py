import cv2
import time
import copy
import numpy as np

from datetime import datetime
from pathlib import Path
from numpy import uint8, fromfile
from cached_property import cached_property

from oashya.tracker import Tracker
from oashya.labels import CLASSINDEX as CI
from oashya.labels import id2label, id2name
from module.logger import logger
from tasks.Hyakkiyakou.agent.focus import Focus
from tasks.Hyakkiyakou.debugger import Debugger


def generate_gaussian_patch(size=(300, 300), mean=0, std_dev=60):
    x = np.linspace(-150, 150, size[1])
    y = np.linspace(-150, 150, size[0])
    x, y = np.meshgrid(x, y)
    z = np.exp(-(((x - mean) ** 2 + (y - mean) ** 2) / (2 * std_dev ** 2)))
    return z


def embed_patch_in_canvas(canvas, patch, position=(0, 0), patch_size=(300, 300)):
    """把热力图补丁按目标中心贴入画布，并裁去超出画布的部分。"""
    canvas_height, canvas_width = 720, 1280
    patch_height, patch_width = patch_size
    pos_x, pos_y = position
    pos_x = max(0, min(pos_x, canvas_width))
    pos_y = max(0, min(pos_y, canvas_width))

    left = pos_x - patch_width // 2
    top = pos_y - patch_height // 2
    x1 = max(0, left)
    y1 = max(0, top)
    x2 = min(canvas_width, left + patch_width)
    y2 = min(canvas_height, top + patch_height)
    embed_w = x2 - x1
    embed_h = y2 - y1
    if embed_w <= 0 or embed_h <= 0:
        logger.warning(f'Cannot embed patch in canvas: ({position})')
        return canvas
    patch_x = x1 - left
    patch_y = y1 - top
    canvas[y1:y2, x1:x2] += patch[patch_y:patch_y + embed_h, patch_x:patch_x + embed_w]
    return canvas


class Agent:
    GAUSSIAN = generate_gaussian_patch()
    # --------------------------------------------------------------------------------

    def __init__(self, strategy: dict = None):
        self.z = np.zeros((720, 1280), dtype=np.float32)
        self.focus: Focus = None
        # 
        strategy: dict = strategy if strategy is not None else {
            # 'weights': [1., 1., 1., 0.6, 0.3, 0.3],
            'priorities': [],
            'invite_friend': False,
            'auto_bean': False
        }
        self.strategy = strategy
        self.weights: list[float] = strategy.get('weights', [1., 0.9, 0.8, 0.7, 0.6, 0.6])
        self.priorities: list[int] = strategy.get('priorities', [])
        self.invite_friend: bool = strategy.get('invite_friend', False)
        self.auto_bean: bool = strategy.get('auto_bean', False)
        #
        self.last_throw_time = datetime.now()
        self.dbg_throw: int = 0
        self.dbg_throw_n: int = 0

    @classmethod
    def gamma(cls, tracks: list[tuple],
              weights: list[float],
              priorities: list[int] = []) -> np.ndarray:
        """
        @param tracks:
        @param weights: sp, ssr, sr, r, n, g
        @param priorities:
        @return:
        """
        z = np.zeros((720, 1280), dtype=np.float32)
        for _id, _class, _conf, _cx, _cy, _w, _h, _v in tracks:
            weight = 1.
            mu = 0.8 + (_cx * 0.2) / 1280
            match _class:
                case _ if CI.MIN_G <= _class <= CI.MAX_G: weight = weights[5]
                case _ if CI.MIN_N <= _class <= CI.MAX_N: weight = weights[4]
                case _ if CI.MIN_R <= _class <= CI.MAX_R:
                    weight = weights[3]
                case _ if CI.MIN_SR <= _class <= CI.MAX_SR: weight = weights[2]
                case _ if CI.MIN_SSR <= _class <= CI.MAX_SSR: weight = 1.5 * weights[1]
                case _ if CI.MIN_SP <= _class <= CI.MAX_SP: weight = 1.5 * weights[0]
                # case CI.BUFF_005:  # freeze
                #     weight = -1.
                #     _cy += 100
                case _: continue
            for priority in priorities:  # 同稀有度内的自定义优先目标
                if priority == _class:
                    weight = 1.7
                    break
            # Weights break ties inside a rarity, never disable a visible card.
            weight = max(0.01, weight)
            z = embed_patch_in_canvas(canvas=z, patch=(mu * weight) * Agent.GAUSSIAN, position=(_cx, _cy))
        return z

    @classmethod
    def argmax_gamma(cls, z: np.ndarray, tracks: list[tuple]) -> Focus | None:
        max_y, max_x = np.unravel_index(np.argmax(z), z.shape)
        max_variance = 2000
        max_index = -1
        for index, track in enumerate(tracks):
            _id, _class, _conf, _cx, _cy, _w, _h, _v = track
            variance = (max_x - _cx)**2 + (max_y - _cy)**2
            if variance < max_variance:
                max_index = index
                max_variance = variance
        if max_index < 0:
            return None
        return Focus(inputs=tracks[max_index])

    def decision(self, tracks: list[tuple], state: list, freeze: bool = False) -> list:
        not_decision = [-1, -1, False, -1]
        if not tracks:
            return not_decision
        # Cache the time interval for scattering beans
        new_time = datetime.now()
        delta_time = 1000 * (new_time - self.last_throw_time).total_seconds()  # ms
        self.check_observe(tracks=tracks)
        if self.focus is None:
            return not_decision
        result = self.focus.decision(tracks=tracks, strategy=self.strategy, state=[delta_time] + state, freeze=freeze)
        if result[2]:
            self.last_throw_time = new_time
            self.dbg_throw += 1
        else:
            self.dbg_throw_n += 1
        return result

    def check_observe(self, tracks: list[tuple]):
        """在画面内按稀有度筛选目标，并在无匹配时清除焦点。"""
        candidates = [track for track in tracks
                      if self.rarity_rank(track[1]) > 0
                      and 0 <= track[3] < 1280 and 0 <= track[4] < 720]
        if not candidates:
            if self.focus is not None:
                logger.info('Focus disappear')
            self.focus = None
            return
        highest_rarity = max(self.rarity_rank(track[1]) for track in candidates)
        candidates = [track for track in candidates if self.rarity_rank(track[1]) == highest_rarity]
        z = Agent.gamma(tracks=candidates, weights=self.weights, priorities=self.priorities)
        focus = Agent.argmax_gamma(z=z, tracks=candidates)
        if focus is None:
            if self.focus is not None:
                logger.info('Focus disappear')
            self.focus = None
            return
        omega = focus.omega(z)
        if self.focus is None or self.focus != focus:
            logger.info(f'Focus changed, now: {id2name(focus._class)}')
            self.focus = focus
            self.focus.set_omega(omega)
        elif self.focus == focus:
            self.focus.update(focus)
            self.focus.set_omega(omega)
        # if Debugger.info_enable:
        #     self.focus.show()

    @staticmethod
    def rarity_rank(class_id: int) -> int:
        for rank, lower, upper in (
            (5, CI.MIN_SP, CI.MAX_SP),
            (4, CI.MIN_SSR, CI.MAX_SSR),
            (3, CI.MIN_SR, CI.MAX_SR),
            (2, CI.MIN_R, CI.MAX_R),
            (1, CI.MIN_N, CI.MAX_N),
            (1, CI.MIN_G, CI.MAX_G),
        ):
            if lower <= class_id <= upper:
                return rank
        return 0

