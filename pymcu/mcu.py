import asyncio

from rtmidi.midiutil import open_midiinput, open_midioutput
from typing import Callable, Awaitable, Union

from .messages.sysex import *
from .messages.fader import *
from .messages.meter import *
from .messages.button import *
from .messages.vpot import *
from .helpers.managed_fader import ManagedFader


PING_INTERVAL = 5 # seconds
RX_INTERVAL = 0.001

N_FADERS = 9


Callback_T = Union[Callable, Awaitable]

async def call_or_await(func: Callback_T, *args, **kwargs) -> None:
    if asyncio.iscoroutinefunction(func):
        await func(*args, **kwargs)
    else:
        func(*args, **kwargs)

class MCUDevice:
    def __init__(self, input_port: str, output_port: str):
        self.tx_queue = asyncio.Queue(maxsize=1024)
        self.response_queue = asyncio.Queue(maxsize=1024)
        self.midi_in, _ = open_midiinput(input_port)
        self.midi_out, _ = open_midioutput(output_port)
        self.connected_status = False
        self.pending_pings = 0

        self.touchless_faders = False

        self.faders = [
            ManagedFader(index=i, update_trigger=self.fader_update_events[i])
            for i in range(N_FADERS)
        ]

        self.on_vpot_event: Callback_T = None
        self.on_raw_fader_event: Callback_T = None
        self.on_managed_fader_event: Callback_T = None
        self.on_button_event: Callback_T = None


    async def _connect_request_producer(self) -> None:
        """
        If we are not currently ping-pong'ing, send a DeviceQuery
        This should result in the device sending a HostConnectionQuery
        The HostConnectionQuery will then start the ping transaction
        """
        while True:
            await self.tx_queue.put(DeviceQuery())
            await asyncio.sleep(PING_INTERVAL)
    

    async def _fader_update_producer(self) -> None:
        """
        Monitor each of the `ManagedFader` objects
        when one has its `update_trigger` set, queue up a `FaderMoveEvent` to update the surface
        This prevents the surface from pulling the fader position back down after releasing
        """
        while True:
            # Wait for any event to be set
            await asyncio.gather(
                *[
                    fader.update_trigger.wait() for fader in self.faders
                ],
                asyncio.FIRST_COMPLETED
            )
            
            # Send the response for the correct one(s)
            for fader in self.faders:
                if fader.update_trigger.is_set():
                    await self.tx_queue.put(
                        FaderMoveEvent(fader.index, fader.latched_value)
                    )
                    fader.update_trigger.clear()
                    if self.on_managed_fader_event:
                        await call_or_await(
                            self.on_managed_fader_event(fader)
                        )
    

    async def _tx_consumer(self) -> None:
        """
        Watch the `tx_queue` and transmit any pending messages
        """
        while True:
            message = await self.tx_queue.get()

            pkt = message.encode()
            self.midi_out.send_message(pkt)

            # Not sure I like this behaviour being here...
            # But if we are sending a NoteOn <technically> it should be followed by an immediate NoteOff.
            if pkt[0] == 0x90:
                pkt[0] = 0x80
                self.midi_out.send_message(pkt)

            self.tx_queue.task_done()


    async def _response_consumer(self) -> None:
        """
        Watch the `response_queue` and handle any requests from the device
        """
        while True:
            message = await self.response_queue.get()
            match type(message):
                case HostConnectionQuery:
                    await self.tx_queue.put(
                        HostConnectionReply(
                            serial_number=message.serial_number,
                            challenge_code=message.challenge_code
                        )
                    )
            
            # ...
            await asyncio.sleep(RX_INTERVAL)
    

    async def _rx_handler(self):
        """
        Read from the MIDI buffer, classify & pass off to the correct handler
        """
        while True:
            await asyncio.sleep(RX_INTERVAL)
            message = self.midi_in.get_message()
            if message:
                match message := message[0]:
                    case 0xF0:
                        self._receive_sysex(message)
                        continue

                    case _ if message[0] & 0xF0 == 0xE0 and self.on_fader_event: 
                        await call_or_await(
                            self.on_fader_event(FaderMoveEvent.from_midi(message))
                        )
                        continue

                    case _ if message[0] & 0xF0 == 0x90 and self.on_button_event:
                        await call_or_await(
                            self.on_button_event(ButtonPressEvent.from_midi(message))
                        )
                        continue

                    case _ if message[0] & 0xF0 == 0xB0:
                        if message[1] == 0x60 and self.on_scrollwheel_event:
                            await call_or_await(
                                self.on_scrollwheel_event(
                                    ScrollWheelMoveEvent.from_midi(message)
                                )
                            )
                        elif self.on_vpot_event:
                            await call_or_await(
                                self.on_vpot_event(VPotMoveEvent.from_midi(message))
                            )
                        continue


    # ===== #

    def _receive_sysex(self, message: list[int]) -> None:
        """
        Rx handler for sysex messages (protocol connection events)

        Args:
            message (list[int]): incoming raw MIDI
        """

        command_byte = message[5]

        if command_byte not in MESSAGE_CLASSES:
            return
        
        message_obj = MESSAGE_CLASSES[command_byte].from_midi(message)

        if message_obj.response_required:
            self.response_queue.put(message_obj)


    # ===== #


    def config_touchless(self, state: bool) -> None:
        """
        Enable or disable touchless fader mode

        Args:
            state (bool): on or off
        """
        if state == self.touchless:
            return

        self.touchless = state
        self.tx_queue.put_nowait(ConfigTouchlessFaders(state=state))
        for fader in self.faders:
            fader.touchless_mode = state


    def config_touch_sensitivity(self, index: int, sensitivity: int) -> None:
        """
        Configure the touch sensitivity of a fader

        Args:
            index (int): Fader index
            sensitivity (int): Sensitivity value

        Raises:
            ValueError: invalid index
            ValueError: invalid sensitivity
        """
        if index < 0 or index > N_FADERS:
            raise ValueError(f"Fader index {index} out of range (0..{N_FADERS})")
        if sensitivity < 0x00 or index > 0x05:
            raise ValueError(f"Sensitivity {sensitivity:02x} out of range (0x00..0x05)")
        
        self.tx_queue.put_nowait(
            ConfigFaderTouchSensitivity(index=index, sensitivity=sensitivity)
        )

    
    def config_channel_meter_mode(self, channel: int, mode: int) -> None:
        """
        Configure the meter mode for a channel

        Args:
            channel (int): Channel index
            mode (int): Config bit map
        """
        self.tx_queue.put_nowait(
            ConfigChannelMeterMode(channel=channel, mode=mode)
        )


    def config_lcd_meter_mode(self, mode: int) -> None:
        """
        Configure the LCD meter mode

        Args:
            mode (int): 0x00: horizontal, 0x01: vertical
        """
        self.tx_queue.put_nowait(
            ConfigLCDMeterMode(mode=mode)
        )

    
    def reset(self) -> None:
        """
        Reset the device
        """
        self.tx_queue.put_nowait(Reset())

    
    def update_timecode_raw(self, char: int, display_offset: int) -> None:
        """
        Update the timecode display with raw text

        Args:
            char (int): Raw character code
            display_offset (int): Offset to write to
        """
        self.tx_queue.put_nowait(
            UpdateTimecodeChar(char=char, display_offset=display_offset)
        )

    
    def update_timecode(self, text: str, display_offset: int = 0, left_to_right: bool = True) -> None:
        for i, char in enumerate(text):
            self.tx_queue.put_nowait(
                UpdateTimecodeChar(
                    char=char,
                    display_offset=display_offset+i,
                    left_to_right=left_to_right
                )
            )


    def update_lcd_raw(self, text: str, display_offset: int = 0) -> None:
        """
        Update the LCD with raw text

        Args:
            text (str): Text to send
            display_offset (int, optional): Offset to write to. Defaults to 0.
        """
        self.tx_queue.put_nowait(
            UpdateLCD(text=text, display_offset=display_offset)
        )


    def update_single_lcd(self, text: str, index: int, line: int, wrap: bool = True) -> None:
        """
        Update a single segment of the LCD

        Args:
            text (str): Text to send
            index (int): Display index
            line (int): Which line to write to
            wrap (bool, optional): If line is 0 and text overflows, wrap to line 1 on the same LCD. Defaults to True.
        """
        sanitised_text = ""
        offset = (index * LCD_CHAR_WIDTH) + (line * 0x38)

        if len(text) > LCD_CHAR_WIDTH:
            if wrap:
                sanitised_text = text[:LCD_CHAR_WIDTH] + "\n" + text[LCD_CHAR_WIDTH:]
            else:
                sanitised_text = text[:LCD_CHAR_WIDTH]

        lines = sanitised_text.split("\n")
        if line == 0:
            self.update_lcd_raw(lines[0], display_offset=offset)
            self.update_lcd_raw(lines[1], display_offset=offset + 0x38)
        else:
            self.update_lcd_raw(lines[0], display_offset=(line * 0x38) + index)


    # ===== #

    async def run(self):
        asyncio.create_task(self._tx_consumer())
        asyncio.create_task(self._rx_handler())
        asyncio.create_task(self._response_consumer())
        asyncio.create_task(self._fader_update_producer())
        asyncio.create_task(self._connect_request_producer())

        while True:
            await asyncio.sleep(1)

    def close(self):
        self.midi_in.close_port()
        self.midi_out.close_port()


if __name__ == "__main__":
    controller = MCUDevice("X-Touch INT", "X-Touch INT")
    controller.on_button_event = print
    controller.on_raw_fader_event = print
    controller.on_vpot_event = print
    asyncio.run(controller.run())