import numpy as np

from rich.table import Table
from rich.text import Text
from cached_property import cached_property

from module.logger import logger

from oashya.labels import id2label, id2name
from oashya.labels import CLASSINDEX as CI

# get buff status
from tasks.Hyakkiyakou.slave.hya_slave import HyaBuff


class Focus:
    THROW_INTERVAL_MS = 250
    FAST_THROW_INTERVAL_MS = 150

    def __init__(self, inputs: list[tuple]):
        self._id: int = inputs[0]
        self._class: int = inputs[1]
        self._conf: int = inputs[2]
        self._cx: int = inputs[3]
        self._cy: int = inputs[4]
        self._w: int = inputs[5]
        self._h: int = inputs[6]
        self._v: float = inputs[7]
        # -----------------------
        self._omega: float = 0.
        self._omega_buff: float = 0.

    def __eq__(self, o):
        return self._id == o._id or o._class == self._class

    def __str__(self):
        return f"""
id: {self._id}
class: {self._class}
label: {id2label(self._class)}
name: {id2name(self._class)}
conf: {self._conf}
xywh: ({self._cx}, {self._cy}, {self._w}, {self._h})
velocity: {self._v}"""

    def omega(self, z):
        __omega = z[self._cy, self._cx]
        self._omega = __omega
        return __omega

    def set_omega(self, value):
        self._omega = value

    def show(self):
        table = Table(show_lines=True)
        table.add_column('Property', header_style="bright_cyan", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")
        table.add_column('Property', header_style="bright_cyan", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")
        table.add_row('id', str(self._id), 'conf', str(self._conf))
        table.add_row('class', str(self._class), 'xywh', f'({self._cx}, {self._cy}, {self._w}, {self._h})')
        table.add_row('label', id2label(self._class), 'velocity', str(self._v))
        table.add_row('name', f'{id2name(self._class)}', 'omega', str(self._omega))
        logger.print(table, justify='center')

    def update(self, focus):
        self._id = focus._id
        self._class = focus._class
        self._conf = focus._conf
        self._cx = focus._cx
        self._cy = focus._cy
        self._w = focus._w
        self._h = focus._h
        self._v = focus._v

    def decision(self, tracks, strategy, state, freeze: bool = False) -> list:

        buff_states = state[4:] if len(state) > 4 else []  # get buff status：state[4:] = buff_0 ~ buff_3，对应 HyaBuff
        has_prob_up = any(b == HyaBuff.BUFF_STATE6 for b in buff_states) # 是否存在“概率UP”buff（HyaBuff.BUFF_STATE6）
        buff_omega, buff_cx, buff_cy, buff_v, buff_class = self.omega_buff(tracks, strategy['invite_friend'], has_prob_up)
        self._omega_buff = buff_omega
        if self._omega > buff_omega:
            target_x = self._cx + self._v * 100 - (self._w // 2)
            target_y = self._cy - 40
        else:
            target_x = buff_cx + buff_v * 100
            target_y = buff_cy - 40  # top left corner
        # Rarity is already ranked by Agent.gamma. Do not select a rare target
        # and then veto it here: that starves every other visible target too.
        _r = self.r(vector=state, omega=self._omega, omega_buff=buff_omega, freeze=freeze)
        throw = True if _r > 0 else False
        # x, y, throw, number
        return [target_x, target_y, throw, 10]

    def omega_buff(self, tracks, invite_friend: bool, has_prob_up: bool) -> float:
        max_omega = 0.
        max_cx = 0
        max_cy = 0
        max_v = 0
        max_class = 0

        focus_is_ssr_sp = (CI.MIN_SSR <= self._class <= CI.MAX_SSR or CI.MIN_SP <= self._class <= CI.MAX_SP)

        for _id, _class, _conf, _cx, _cy, _w, _h, _v in tracks:
            _current_omega = 0.
            match _class:
                case CI.BUFF_004: _current_omega = 2.2
                case CI.BUFF_006: _current_omega = 2.0
                case CI.BUFF_007: _current_omega = 2.0 if invite_friend and _cx <= 1000 else 0
                case CI.BUFF_002: _current_omega = 2.0 if self._omega >= 1.5 else 0
                case CI.BUFF_003: _current_omega = 2.0 if self._omega >= 1.5 and _cx <= 640 else 0
                # case CI.BUFF_005: _current_omega = max(self._omega + 0.1, 3.0) if focus_is_ssr_sp and has_prob_up else 0 # 冻住，不许跑
                case _: pass
            if _current_omega > max_omega:
                max_omega = _current_omega
                max_cx = _cx
                max_cy = _cy
                max_v = _v
                max_class = _class
        return max_omega, max_cx, max_cy, max_v, max_class
            
    @classmethod
    def r(cls, vector: list, omega: float, omega_buff: float, freeze: bool = False) -> float:
        # Spend beans on a valid selected target instead of saving them for
        # probability buffs or an estimated future shikigami distribution.
        if freeze or vector[1] <= 0:
            return -1.0
        buff_states = vector[4:]
        interval = cls.FAST_THROW_INTERVAL_MS if HyaBuff.BUFF_STATE3 in buff_states else cls.THROW_INTERVAL_MS
        if vector[0] < interval:
            return -1.0
        return max(omega, omega_buff)

