from dataclasses import dataclass, field
from asyncio import Event

from ..messages.fader import FaderMoveEvent
from ..messages.button import ButtonPressEvent

@dataclass
class ManagedFader():
    index: int = field()
    touchless_mode: bool = field(default=False)
    latched_value: int = 0
    raw_value: int = 0
    is_touched: bool = False

    def __post_init__(self):
        self.update_trigger = Event()

    def touch(self, event: ButtonPressEvent) -> None:
        if event.state:
            self.is_touched = True
        else:
            self.is_touched = False
            self.latched_value = self.raw_value
            self.update_trigger.set()
    
    def update(self, event: FaderMoveEvent) -> None:
        if self.is_touched or not self.touchless_mode:
            self.raw_value = event.position
        
    def set_position(self, position: int) -> None:
        self.latched_value = position
        self.update_trigger.set()
