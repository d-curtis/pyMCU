from dataclasses import dataclass, field

@dataclass
class UpdateMeter():
    """
    Host -> Device

    Uses `Channel Pressure` (0xD0) messages
    The `value` field is divided into nibbles:
    - most significant nibble: channel strip ID (0..7)
    - least significant nibble: state of VU meter

    Values 0..-60 set LEDs

    values above 0 are used to pack in some extra flags:
    1: ? but there's a message code for it; documented as "100%"
    254: set overload
    255: clear overload

    Args:
        index: Channel strip ID (0..7)
        value: dB value
    """
    index: int = field()
    value: int = field()
    data_byte: int = None

    METER_THRESHOLDS = {
        0x0F: lambda x: x == 0xFF,
        0x0E: lambda x: x == 0xFE,
        0x0D: lambda x: x > 0,
        0x0C: lambda x: x == 0,
        0x0B: lambda x: x >= -2,
        0x0A: lambda x: x >= -4,
        0x09: lambda x: x >= -6,
        0x08: lambda x: x >= -8,
        0x07: lambda x: x >= -10,
        0x06: lambda x: x >= -14,
        0x05: lambda x: x >= -20,
        0x04: lambda x: x >= -30,
        0x03: lambda x: x >= -40,
        0x02: lambda x: x >= -50,
        0x01: lambda x: x >= -60,
        0x00: lambda x: x < -60
    }

    def encode(self):
        return [0xD0, self.data_byte]

    def __post_init__(self):
        lsn: int = 0

        for nibble, condition in self.METER_THRESHOLDS.items():
            if condition(self.value):
                lsn = nibble
                break
        
        self.data_byte = self.index << 4 | lsn
