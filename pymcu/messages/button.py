from dataclasses import dataclass, field
from .hardware_mapping import NOTE_MAP

LED_OFF = 0x00
LED_BLINK = 0x01
LED_ON = 0x7F

@dataclass
class SetLED():
    index: int = field()
    state: int = field()

    name: str = None

    def __post_init__(self):
        self.name = NOTE_MAP.get(self.index, "Unknown")

    def encode(self):
        return [0x90, self.index, self.state]


@dataclass
class ButtonPressEvent():
    index: int = field()
    state: int = field()

    name: str = None

    def __post_init__(self):
        self.name = NOTE_MAP.get(self.index, "Unknown")

    @classmethod
    def from_midi(cls, data):
        return cls(index=data[1], state=data[2])