from .button import *
from .fader import *
from .hardware_mapping import *
from .meter import *
from .sysex import *
from .vpot import *

__all__ = [
    "FaderMoveEvent",
    "ButtonPressEvent",
    "SetLED",
    "NOTE_MAP"
]

def mcu_from_midi(data: list[int]):
    """
    Decode a MIDI message into a MCU message object

    Args:
        data: MIDI message data
    """
    # UNTESTED
    if data[0] == SOX and data[-1] == EOX:
        # SysEx
        if data[1:5] != MCU_HEADER:
            raise ValueError(f"Invalid SysEx header: {data[1:5]}")
        
        if _type := MESSAGE_CLASSES.get(data[5]) is not None:
            return _type.from_midi(data)
        else:
            raise ValueError(f"Unknown SysEx command type: {data[5]}")
