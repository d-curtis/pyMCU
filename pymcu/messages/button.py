from dataclasses import dataclass, field

LED_OFF = 0x00
LED_BLINK = 0x01
LED_ON = 0x7F


@dataclass
class SetLED():
    index: int = field()
    state: int = field()

    def encode(self):
        return [0x90, self.index, self.state]

