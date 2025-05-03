from ..messages import *
from dataclasses import dataclass, field

from collections import namedtuple

MIDIMessage = list[int]

FaderData = namedtuple('FaderData', ['position', 'touched'])
LEDData = namedtuple('LEDData', ['state'])
MeterData = namedtuple('MeterData', ['value'])

@dataclass
class MCUSurfaceModel():
    """
    Represents the current state of LEDs / pots / faders
    """
    faders: list[FaderData] = field(default_factory=lambda: [FaderData(0, False)  for _ in range(8)])
    leds: list[LEDData] = field(default_factory=lambda: [LEDData(0) for _ in range(len(NOTE_MAP))])

    def update(self, message: MIDIMessage):
        """
        Update the surface model with a MIDI message
        """
        try:
            event = SetLED.from_midi(message)
            print(event)
        except:
            return
        try:
            self.buttons[event.index] = LEDData(event.state)
        except IndexError:
            pass

