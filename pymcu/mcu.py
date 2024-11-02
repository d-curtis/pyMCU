import asyncio

from rtmidi.midiutil import open_midiinput, open_midioutput
from typing import Callable, Awaitable, Union

from messages.sysex import *
from messages.fader import *
from messages.meter import *
from messages.button import *
from messages.vpot import *


PING_INTERVAL = 5 # seconds
RX_INTERVAL = 0.001

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

        self.on_vpot_event: Callback_T = None
        self.on_fader_event: Callback_T = None
        self.on_button_event: Callback_T = None


    async def connect_request_producer(self) -> None:
        """
        If we are not currently ping-pong'ing, send a DeviceQuery
        This should result in the device sending a HostConnectionQuery
        The HostConnectionQuery will then start the ping transaction
        """
        while True:
            await self.tx_queue.put(DeviceQuery())
            await asyncio.sleep(PING_INTERVAL)
    

    async def tx_consumer(self) -> None:
        """
        Watch the `tx_queue` and transmit any pending messages
        """
        print("Tx consumer started")
        while True:
            message = await self.tx_queue.get()
            print(message)

            pkt = message.encode()
            self.midi_out.send_message(pkt)

            # Not sure I like this behaviour being here...
            # But if we are sending a NoteOn <technically> it should be followed by an immediate NoteOff.
            if pkt[0] == 0x90:
                pkt[0] = 0x80
                self.midi_out.send_message(pkt)

            self.tx_queue.task_done()


    async def response_consumer(self) -> None:
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
    

    async def rx_handler(self):
        """
        Read from the MIDI buffer, classify & pass off to the correct handler
        """
        while True:
            await asyncio.sleep(RX_INTERVAL)
            message = self.midi_in.get_message()
            if message:
                match message := message[0]:
                    case 0xF0:
                        self.receive_sysex(message)
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

    def receive_sysex(self, message: list[int]) -> None:
        """
        Rx handler for sysex messages (protocol connection events)

        Args:
            message (list[int]): incoming raw MIDI
        """

        command_byte = message[5]

        if command_byte not in MESSAGE_CLASSES:
            print(f"(receive_sysex): Unknown: {message}")
            return
        
        message_obj = MESSAGE_CLASSES[command_byte].from_midi(message)

        if message_obj.response_required:
            self.response_queue.put(message_obj)

        ...

    
    # ===== #

    async def run(self):
        asyncio.create_task(self.tx_consumer())
        asyncio.create_task(self.rx_handler())
        asyncio.create_task(self.response_consumer())

        while True:
            await asyncio.sleep(1)

    def close(self):
        self.midi_in.close_port()
        self.midi_out.close_port()


if __name__ == "__main__":
    controller = MCUDevice("X-Touch INT", "X-Touch INT")
    asyncio.run(controller.run())