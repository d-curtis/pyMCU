from dataclasses import dataclass, field

@dataclass
class FaderMoveEvent():
    """
    Faders use `pitch bend` messages for position to encode 14 bits over 2 bytes.
    Unless the device is operating in touchless faders mode, this message must be
    sandwiched by touch/release events for it to be counted.
    """

    index: int = field()
    position: int = field()

    def encode(self):
        return [
            0b1110_0000 | self.index,   # Message type & channel
            self.position & 0x7F,       # Position LSB
            (self.position >> 7) & 0x7F # Position MSB
        ]

    @classmethod
    def from_midi(cls, data):
        return cls(
            index=(data[0] & 0x0F),
            position=(
                (data[2] & 0x7F) << 7 | (data[1] & 0x7F)
            )
        )
