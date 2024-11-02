# https://github.com/NicoG60/TouchMCU/blob/main/doc/mackie_control_protocol.md

from dataclasses import dataclass, field

SOX = [0xF0]
MCU_HEADER = [0x00, 0x00, 0x66, 0x14]
BEH_HEADER = [0x00, 0x00, 0x66, 0x58]
EOX = [0xF7]

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


#################### Connection Management ####################

@dataclass
class DeviceQuery(MCUBase):
    """
    Host -> Device
    0 parameter bytes
    """
    command = 0x00

    def encode(self) -> list[int]:
        return SOX + MCU_HEADER + [self.command] + EOX

    def to_midi(self):
        return SOX + MCU_HEADER + [self.command] + EOX


@dataclass
class HostConnectionQuery(MCUBase):
    """
    Device -> Host
    11 parameter bytes (7 bytes serial number, 4 bytes challenge code)
    """
    command: int = 0x01
    response_required: bool = True
    serial_number: str = field(default=None)
    challenge_code: list[int] = field(default_factory=list)

    def encode(self) -> list[int]:
        raise NotImplementedError

    @classmethod
    def from_midi(cls, syx: list[int]):
        serial_number = "".join([chr(x) for x in syx[6:13]])
        challenge_code = syx[14:22]
        return cls(serial_number=serial_number, challenge_code=challenge_code)


@dataclass
class HostConnectionReply(MCUBase):
    """
    Host -> Device
    11 parameter bytes (7 bytes serial number, 4 bytes response code)
    """
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

    def encode(self) -> list[int]:
        return \
            SOX \
            + MCU_HEADER \
            + [self.command] \
            + [ord(x) for x in self.serial_number] \
            + self.response_code \
            + EOX

    @classmethod
    def from_midi(cls, syx: list[int]):
        raise NotImplementedError


@dataclass
class HostConnectionConfirmation(MCUBase):
    """
    Device -> Host
    7 parameter bytes (7 bytes serial number)
    """
    serial_number: str = field(default=None)
    command: int = 0x03

    def encode(self) -> list[int]:
        raise NotImplementedError

    @classmethod
    def from_midi(cls, syx: list[int]):
        serial_number = "".join([chr(x) for x in syx[6:13]])
        return cls(serial_number=serial_number)


@dataclass
class HostConnectionError(MCUBase):
    """
    Device -> Host
    7 parameter bytes (7 bytes serial number)

    Displays << SECURITY UNLOCK FAILED SHUTTING DOWN >> and refuses further messages
    """
    serial_number: str = field(default=None)
    command: int = 0x04

    def encode(self) -> list[int]:
        raise NotImplementedError

    @classmethod
    def from_midi(cls, syx: list[int]):
        serial_number = "".join([chr(x) for x in syx[6:13]])
        return cls(serial_number=serial_number)


####################        Config         ####################


@dataclass
class ConfigTransportButtonClick(MCUBase):
    """
    Host -> Device
    1 parameter byte (state 0x00 | 0x01)

    0x00: No transport button click
    0x01: Transport button click (default)
    """
    command: int = 0x0A

    def encode(self) -> list[int]:
        raise NotImplementedError

    @classmethod
    def from_midi(cls, syx: list[int]):
        raise NotImplementedError


@dataclass
class ConfigLCDBacklightSaver(MCUBase):
    """
    Host -> Device
    1 parameter byte (state)

    0x00: LCD Backlight off
    0x01 .. 0x7F: LCD backlight on, timeout in minutes (default: 0x0F = 15 minutes)
    """
    command: int = 0x0B

    def encode(self) -> list[int]:
        raise NotImplementedError

    @classmethod
    def from_midi(cls, syx: list[int]):
        raise NotImplementedError


@dataclass
class ConfigTouchlessFaders(MCUBase):
    """
    Host -> Device
    1 parameter byte (state)

    0x00: fader movements only transmitted if touched
    0x01: fader movements always transmitted even if capacitive touch is not detected (default)
    """
    command: int = 0x0C
    state: bool = field(default=None)

    def encode(self) -> list[int]:
        return SOX + MCU_HEADER + [self.command, int(self.state)] + EOX

    @classmethod
    def from_midi(cls, syx: list[int]):
        raise NotImplementedError


@dataclass
class ConfigFaderTouchSensitivity(MCUBase):
    """
    Host -> Device
    2 parameter bytes (1 byte fader, 1 byte sensitivity)

    fader ID (0x00 .. 0x07; master fader: 0x08)
    touch sensitivity (0x00 .. 0x05; default: 0x03)
    """
    command: int = 0x0E

    def encode(self) -> list[int]:
       return SOX + MCU_HEADER + [self.command, self.index, self.sensitivity] + EOX

    @classmethod
    def from_midi(cls, syx: list[int]):
        raise NotImplementedError


@dataclass
class UpdateLCD(MCUBase):
    """
    Host -> Device
    2 - 113 parameter bytes (1 byte display offset, 1..112 bytes characters)

    Display offset (0x00..0x37 upper line, 0x38..0x6F lower line)
    Text (ASCII characters, will wrap lines)
    """
    text: str = field(default=None)
    display_offset: int = field(default=0)
    raw_text: list[int] = field(default_factory=list)
    command: int = 0x12
    response_required = False

    def __post_init__(self):
        if not self.raw_text:
            self.raw_text = [ord(x) for x in self.text]

    def encode(self) -> list[int]:
        return \
            SOX \
            + MCU_HEADER \
            + [self.command] \
            + [self.display_offset] \
            + self.raw_text \
            + EOX

LCD_OFF = 0
LCD_RED = 1
LCD_GREEN = 2
LCD_YELLOW = 3
LCD_BLUE = 4
LCD_PINK = 5
LCD_CYAN = 6
LCD_WHITE = 7

@dataclass
class UpdateLCDColour(MCUBase):
    """
    Host -> Device
    """
    colours: list[int] = field(default_factory=list)
    command: int = 0x72

    def __post_init__(self):
        if len(self.colours) != 8:
            print(self.colours)
            raise ValueError("Need 8 colours")

    def encode(self) -> list[int]:
        return \
            SOX \
            + MCU_HEADER \
            + [self.command] \
            + self.colours \
            + EOX


@dataclass
class FirmwareVersionRequest(MCUBase):
    """
    Host -> Device
    1 parameter byte (0x00)
    """
    command: int = 0x13
    response_required = True

    def encode(self) -> list[int]:
        return SOX + MCU_HEADER + [self.command, 0x00] + EOX

    @classmethod
    def from_midi(cls, syx: list[int]):
        raise NotImplementedError


@dataclass
class FirmwareVersionResponse(MCUBase):
    """
    Device -> Host
    5 parameter bytes (firmware version, ASCII text)
    """
    command: int = 0x14
    firmware_version: str = field(default=None)

    def encode(self) -> list[int]:
        raise NotImplementedError

    @classmethod
    def from_midi(cls, syx: list[int]):
        raise NotImplementedError


@dataclass
class ConfigChannelMeterMode(MCUBase):
    """
    Host -> Device
    2 parameter bytes (1 byte channel, 1 byte mode)

    channel ID (0x00 .. 0x07)
    mode (config bit map: 0b00000lps, l: level meter, p: peak hold, s: signal LED)
    """
    command: int = 0x15
    level_meter: bool = field(default=True)
    peak_hold: bool = field(default=True)
    signal_led: bool = field(default=True)

    def encode(self) -> list[int]:
        return SOX \
            + MCU_HEADER \
            + [self.command] \
            + [int(self.level_meter) << 2 | int(self.peak_hold) << 1 | int(self.signal_led)] \
            + EOX

    @classmethod
    def from_midi(cls, syx: list[int]):
        raise NotImplementedError


@dataclass
class ConfigLCDMeterMode(MCUBase):
    """
    Host -> Device
    1 parameter byte (mode)

    mode (0x00: horizontal, 0x01: vertical)
    """
    command: int = 0x16
    mode: int = field(default=0)

    def encode(self) -> list[int]:
        raise NotImplementedError

    @classmethod
    def from_midi(cls, syx: list[int]):
        raise NotImplementedError


@dataclass
class Reset(MCUBase):
    """
    Host -> Device
    0 parameter bytes
    """
    command: int = 0x63

    def encode(self) -> list[int]:
        return SOX + MCU_HEADER + [self.command] + EOX

    @classmethod
    def from_midi(cls, syx: list[int]):
        raise NotImplementedError


@dataclass
class UpdateTimecodeChar(MCUBase):
    char: str = field(default=None)
    raw_char: list[int] = field(default_factory=list)
    display_offset: int = field(default=0)
    left_to_right: bool = False

    def __post_init__(self):
        if not self.raw_char:
            self.raw_char = SEGMENT_CHARS.get(self.char[0].lower(), 0x00)

    def encode(self) -> list[int]:
        if not self.left_to_right:
            return [0xB0, self.display_offset + 0x40, self.raw_char]
        else:
            return [0xB0, 0x4B - self.display_offset, self.raw_char]


MESSAGE_CLASSES = {
    0x00: DeviceQuery,
    0x01: HostConnectionQuery,
    0x02: HostConnectionReply,
    0x03: HostConnectionConfirmation,
    0x04: HostConnectionError,
    0x0A: ConfigTransportButtonClick,
    0x0B: ConfigLCDBacklightSaver,
    0x0C: ConfigTouchlessFaders,
    0x0E: ConfigFaderTouchSensitivity,
    0x12: UpdateLCD,
    0x13: FirmwareVersionRequest,
    0x14: FirmwareVersionResponse,
    0x20: ConfigChannelMeterMode,
    0x21: ConfigLCDMeterMode,
    0x63: Reset,
}