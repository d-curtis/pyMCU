# https://github.com/NicoG60/TouchMCU/blob/main/doc/mackie_control_protocol.md

from dataclasses import dataclass, field

SOX = [0xF0]
MCU_HEADER = [0x00, 0x00, 0x66, 0x14]
EOX = [0xF7]

MAGIC_PACKET = [0xF0, 0x7E, 0x00, 0x06, 0x01, 0xF7]

DEVICE_QUERY = [0x00]
CONNECTION_QUERY = [0x90, 0x00, 0x7F]

SEGMENT_CHARS = {
    " ": 0x00, "a": 0x01, "b": 0x02, "c": 0x03,
    "d": 0x04, "e": 0x05, "f": 0x06, "g": 0x07,
    "h": 0x08, "i": 0x09, "j": 0x0A, "k": 0x0B,
    "l": 0x0C, "m": 0x0D, "n": 0x0E, "o": 0x0F,
    "p": 0x10, "q": 0x11, "r": 0x12, "s": 0x13,
    "t": 0x14, "u": 0x15, "v": 0x16, "w": 0x17,
    "x": 0x18, "y": 0x19, "z": 0x1A, "_": 0x1F,
    "\"": 0x22, "'": 0x27, ",": 0x2C, "-": 0x2D,
    ".": 0x40, "0": 0x30, "1": 0x31, "2": 0x32,
    "3": 0x33, "4": 0x34, "5": 0x35, "6": 0x36,
    "7": 0x37, "8": 0x38, "9": 0x39,
}

def hex_string(data: list[int]):
    """Print the data as a hex string."""
    return(" ".join(f"{x:02X}" for x in data))

@dataclass
class MCUBase:
    response_required: bool = False


@dataclass
class DeviceQuery(MCUBase):
    command = 0x00

    def to_syx(self):
        return SOX + MCU_HEADER + DEVICE_QUERY + EOX


@dataclass
class HostConnectionQuery(MCUBase):
    command: int = 0x01
    response_required: bool = True
    serial_number: str = field(default=None)
    challenge_code: list[int] = field(default_factory=list)

    def to_syx(self) -> list[int]:
        raise NotImplementedError

    @classmethod
    def from_syx(cls, syx: list[int]):
        serial_number = "".join([chr(x) for x in syx[6:13]])
        challenge_code = syx[14:22]
        return cls(serial_number=serial_number, challenge_code=challenge_code)


@dataclass
class HostConnectionReply(MCUBase):
    serial_number: str = field(default=None)
    challenge_code: list[int] = field(default=None)
    response_code: list[int] = field(default_factory=list)
    command: int = 0x02

    def __post_init__(self):
        c = self.challenge_code
        self.response_code = [
            0x7F & (c[0] + (c[1] ^ 0x0A ) - c[3]),
            0x7F & ((c[2] >> 4) ^ (c[0] + c[3])),
            0x7F & (c[3] - (c[2] << 2) ^ (c[0] | c[1])),
            0x7F & (c[1] - c[2] + (0xF0 ^ (c[3] << 4)))
        ]

    def to_syx(self) -> list[int]:
        return \
            SOX \
            + MCU_HEADER \
            + [self.command] \
            + [ord(x) for x in self.serial_number] \
            + self.response_code \
            + EOX

    @classmethod
    def from_syx(cls, syx: list[int]):
        raise NotImplementedError

@dataclass
class UpdateLCD(MCUBase):
    text: str = field(default=None)
    display_offset: int = field(default=0)
    raw_text: list[int] = field(default_factory=list)
    command: int = 0x12
    response_required = False

    def __post_init__(self):
        if not self.raw_text:
            self.raw_text = [ord(x) for x in self.text]
    
    def to_syx(self) -> list[int]:
        return \
            SOX \
            + MCU_HEADER \
            + [self.command] \
            + [self.display_offset] \
            + self.raw_text \
            + EOX

@dataclass
class UpdateTimecodeChar(MCUBase):
    char: str = field(default=None)
    raw_char: list[int] = field(default_factory=list)
    display_offset: int = field(default=0)
    response_required = False
    left_to_right: bool = False

    def __post_init__(self):
        if not self.raw_char:
            self.raw_char = SEGMENT_CHARS.get(self.char[0].lower(), 0x00)
    
    def to_syx(self) -> list[int]:
        if not self.left_to_right:
            return [0xB0, self.display_offset + 0x40, self.raw_char]
        else:
            return [0xB0, 0x4B - self.display_offset, self.raw_char]

MESSAGE_CLASSES = {
    0x00: DeviceQuery,
    0x01: HostConnectionQuery,
    0x02: HostConnectionReply,
}