import numpy as np

from rich.table import Table
from rich.text import Text
from cached_property import cached_property

from module.logger import logger

from oashya.labels import id2label, id2name

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
        height, width = z.shape[:2]
        if not (0 <= self._cy < height and 0 <= self._cx < width):
            self._omega = 0.
            return self._omega
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
        target_x = min(1279, max(0, self._cx + self._v * 100 - (self._w // 2)))
        target_y = min(719, max(0, self._cy - 40))
        # Agent has already chosen the highest-rarity visible shikigami.
        # A buff must neither replace that target nor gate throwing at it.
        _r = self.r(vector=state, omega=self._omega, omega_buff=0, freeze=freeze)
        throw = True if _r > 0 else False
        # x, y, throw, number
        return [target_x, target_y, throw, 5]

    @classmethod
    def r(cls, vector: list, omega: float, omega_buff: float, freeze: bool = False) -> float:
        # Spend beans on a valid selected target instead of saving them for
        # probability buffs or an estimated future shikigami distribution.
        if vector[1] <= 0:
            return -1.0
        buff_states = vector[4:]
        interval = cls.FAST_THROW_INTERVAL_MS if HyaBuff.BUFF_STATE3 in buff_states else cls.THROW_INTERVAL_MS
        if vector[0] < interval:
            return -1.0
        return max(omega, omega_buff)

