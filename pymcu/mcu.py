import asyncio

from rtmidi.midiutil import open_midiinput, open_midioutput
from rtmidi import MidiIn, MidiOut
from typing import Callable, Awaitable, Union, Optional

from .messages.sysex import *
from .messages.fader import *
from .messages.meter import *
from .messages.button import *
from .messages.vpot import *
from .helpers.managed_fader import ManagedFader
from .helpers.simulator import MCUSimulatorGUI
from .helpers.surface_model import MCUSurfaceModel


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
    def __init__(self, input_port: Union[str, MidiIn], output_port: Union[str, MidiOut], run_simulator: bool = False):
        self.tx_queue = asyncio.Queue(maxsize=1024)
        self.response_queue = asyncio.Queue(maxsize=1024)
        self.midi_in, _ = open_midiinput(input_port) if type(input_port) is str else (input_port, None)
        self.midi_out, _ = open_midioutput(output_port) if type(output_port) is str else (output_port, None)
        self.connected_status = False
        self.pending_pings = 0

        self.touchless_faders = False

        self.faders = [
            ManagedFader(index=i)
            for i in range(N_FADERS)
        ]

        self.lcd_colours = [LCD_WHITE] * 8

        self.on_vpot_event: Callback_T = None
        self.on_raw_fader_event: Callback_T = None
        self.on_managed_fader_event: Callback_T = None
        self.on_button_event: Callback_T = None
        self.on_scrollwheel_event: Callback_T = None

        if run_simulator:
            self.simulator_model = MCUSurfaceModel()
            self.simulator = MCUSimulatorGUI(surface=self.simulator_model)
        else:
            self.simulator_model = None
            self.simulator = None


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
            await asyncio.wait(
                [
                    asyncio.create_task(fader.update_trigger.wait()) for fader in self.faders
                ],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Send the response for the correct one(s)
            for fader in self.faders:
                if fader.update_trigger.is_set():
                    await self.tx_queue.put(
                        FaderMoveEvent(index=fader.index, position=fader.latched_value)
                    )
                    fader.update_trigger.clear()
                    if self.on_managed_fader_event:
                        await call_or_await(
                            self.on_managed_fader_event, fader
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
                print(message)
                if self.simulator_model:
                    self.simulator_model.update(message[0])
                match message := message[0]:
                    case 0xF0:
                        self._receive_sysex(message)
                        continue

                    case _ if message[0] & 0xF0 == 0xE0:
                        event = FaderMoveEvent.from_midi(message)
                        self.faders[event.index].update(event)
                        if self.on_raw_fader_event: 
                            await call_or_await(
                                self.on_raw_fader_event, event
                            )
                        continue

                    case _ if message[0] & 0xF0 == 0x90:
                        event = ButtonPressEvent.from_midi(message)
                        if event.index in range(104, 113):
                            self.faders[event.index - 104].touch(event)
                        if self.on_button_event:
                            await call_or_await(
                                self.on_button_event, ButtonPressEvent.from_midi(message)
                            )
                        continue

                    case _ if message[0] & 0xF0 == 0xB0:
                        if message[1] & 0x0F == 12 and self.on_scrollwheel_event:
                            await call_or_await(
                                self.on_scrollwheel_event,
                                    ScrollWheelMoveEvent.from_midi(message)
                            )
                        elif self.on_vpot_event:
                            await call_or_await(
                                self.on_vpot_event, VPotMoveEvent.from_midi(message)
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


    def update_single_lcd(self, index: int, text: Union[str, list[str]], line=0) -> None:
        """
        Update a single segment of the LCD

        Args:
            index (int): Display index
            text (Union[str, list[str]]): Text to send, either line 0 or list of both lines
            line (int): Which line to write to if text is a string
        """
        if type(text) is int:
            text = str(text)
        if type(text) is str:
            offset = (index * LCD_CHAR_WIDTH) + (line * 0x38)
            self.update_lcd_raw(f"{text[:LCD_CHAR_WIDTH]:^{LCD_CHAR_WIDTH}}", display_offset=offset)
            return

        for line, line_text in enumerate(text):
            if line > 1:
                return
            offset = (index * LCD_CHAR_WIDTH) + (line * 0x38)
            self.update_lcd_raw(f"{line_text[:LCD_CHAR_WIDTH]:^{LCD_CHAR_WIDTH}}", display_offset=offset)


    def update_lcd_colour(self, index: int, colour: int) -> None:
        """
        Update the colour of a single LCD

        Args:
            index (int): LCD index
            colour (int): Colour index
        """
        if colour < 0 or colour > 0x0F:
            return
        self.lcd_colours[index] = colour
        self.tx_queue.put_nowait(
            UpdateLCDColour(colours=self.lcd_colours)
        )


    def update_lcd_colours(self, colours: list[int]) -> None:
        """
        Update the colour of all LCDs

        Args:
            colours (list[int]): Colour index
        """
        self.lcd_colours = colours
        self.tx_queue.put_nowait(
            UpdateLCDColour(colours=self.lcd_colours)
        )

    
    def set_led(self, index: int, state: int) -> None:
        """
        Set the state of an LED

        Args:
            index (int): LED index
            state (int): State
        """
        self.tx_queue.put_nowait(
            SetLED(index=index, state=state)
        )
    

    def set_fader(self, index: int, position: int) -> None:
        """
        Set the position of a fader

        Args:
            index (int): Fader index
            position (int): Position
        """
        self.faders[index].set_position(position)
        self.tx_queue.put_nowait(FaderMoveEvent(index=index, position=position))


    def set_vpot_led(self, index: int, mode: int, value: int, extra: bool = False) -> None:
        """
        Set the state of a VPot LED

        Args:
            index (int): VPot index
            mode (int): LED ring mode (single, fill-centre, fill-left, width)
            value (int): Value
            extra (bool, optional): Extra LED. Defaults to False.
        """
        self.tx_queue.put_nowait(
            SetVPotLED(index=index, mode=mode, value=value, extra=extra)
        )

    # ===== #


    async def run(self):
        asyncio.create_task(self._tx_consumer())
        asyncio.create_task(self._rx_handler())
        asyncio.create_task(self._response_consumer())
        asyncio.create_task(self._fader_update_producer())
        asyncio.create_task(self._connect_request_producer())
        if self.simulator:
            asyncio.create_task(self.simulator.run())

        while True:
            await asyncio.sleep(1)

    def close(self):
        self.midi_in.close_port()
        self.midi_out.close_port()



if __name__ == "__main__":
    inport, _ = open_midiinput("X-Touch INT")
    outport, _ = open_midioutput("X-Touch INT")
    controller = MCUDevice(inport, outport, run_simulator=True)

    # ...As an example

    def demo_button(event: ButtonPressEvent) -> None:
        if controller.simulator_model:
            controller.simulator_model.update(event)
        if event.index in range(32, 40):
            controller.faders[event.index - 32].set_position(0x3FFF if event.state else 0)
    
    def demo_vpot(event: VPotMoveEvent) -> None:
        if event.index in range(0, 8):
            controller.faders[event.index].set_position(
                controller.faders[event.index].latched_value + (event.delta * 20)
            )
            controller.update_lcd_colour(index=event.index, colour=controller.lcd_colours[event.index] + event.delta)
    
    def demo_fader(event: ManagedFader) -> None:
        controller.update_timecode(f"Monitor A", display_offset=2)
    
    colour_idx = 0
    def demo_wheel(event: ScrollWheelMoveEvent) -> None:
        global colour_idx
        colour_idx += event.delta
        print(colour_idx)
        controller.tx_queue.put_nowait(UpdateLCDColour(colours=[colour_idx]*8))


    controller.on_button_event = demo_button
#    controller.on_raw_fader_event = demo_fader
#    controller.on_managed_fader_event = print
#    controller.on_vpot_event = demo_vpot
#    controller.on_scrollwheel_event = demo_wheel

    controller.update_lcd_colours([LCD_PINK]*8)

#    controller.update_single_lcd("X2P Gtr\nDnte 01", index=0)
#    controller.update_single_lcd("X2P 2\nDnte 02", index=1)
#    controller.update_single_lcd("MP8R 7\nDnte 31", index=2)
#    controller.update_single_lcd("MP8R 8\nDnte 31", index=3)
#    controller.update_single_lcd("Peak L\nAnlg 15", index=4)
#    controller.update_single_lcd("Peak R\nAnlg 16", index=5)
#    controller.update_single_lcd("Sample\nLoopB 1", index=6)
#    controller.update_single_lcd("Kemp DI\nSPDIF 1", index=7)



    asyncio.run(controller.run())
