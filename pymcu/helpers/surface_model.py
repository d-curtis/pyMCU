from ..messages import *
from dataclasses import dataclass, field

MIDIMessage = list[int]

@dataclass
class MCUSurfaceModel():
    """
    Represents the current state of LEDs / pots / faders
    """

    def __init__(self):
        pass

    def update(self, message: MIDIMessage):
        """
        Update the surface model with a MIDI message
        """
        pass
