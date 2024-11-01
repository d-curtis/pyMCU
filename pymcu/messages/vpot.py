from dataclasses import dataclass, field

@dataclass
class VPotMoveEvent():
    index: int = field()
    delta: int = field()

    @classmethod
    def from_midi(cls, data):
        return cls(
            index=(data[1] & 0x0F),
            delta=(data[2] & 0x7F)
        )
    
    def encode(self):
        return [
            0xB0,
            0x10 | self.index,
            self.delta
        ]


RING_MODE_SINGLE = 0b00
RING_MODE_FILL_CENTRE = 0b01
RING_MODE_FILL_LEFT = 0b10
RING_MODE_WIDTH = 0b11

@dataclass
class SetVPotLED():
    """
    Update the LED ring on a VPot

    Args:
        index: VPot index
        mode: LED ring mode (single, fill-centre, fill-left, width)
        value: LED ring value
        extra: Bonus LED underneath the encoder
    """
    index: int = field()
    mode: int = field()
    value: int = field()
    extra: bool = field()

    def encode(self) -> list[int]:
        assert self.mode >= 0 and self.mode <= 3
        
        # Bit 7 is always 0
        # Bit 6 is the on/off toggle of the little LED underneath the encoder.
        # Bits 5 and 4 represent a Mode value
        # Bits 3 to 0 represent the Value
        value_byte = (self.value & 0x0F) | (self.mode << 4) | (self.extra << 6)

        return [
            0xB0, # Control Change 
            0x30 | self.index, # Index
            value_byte, # Encoded mode, extra LED, and value
        ]

