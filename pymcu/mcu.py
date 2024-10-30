import rtmidi
import asyncio

from rtmidi.midiutil import open_midiinput, open_midioutput

from messages.sysex import *
from messages.fader import *
from messages.meter import *

PING_INTERVAL = 5 # seconds
RX_INTERVAL = 0.001

class MCUDevice:
    def __init__(self, input_port: str, output_port: str):
        self.tx_queue = asyncio.Queue(maxsize=1024)
        self.response_queue = asyncio.Queue(maxsize=1024)
        self.midi_in, _ = open_midiinput(input_port)
        self.midi_out, _ = open_midioutput(output_port)
        self.connected_status = False
        self.pending_pings = 0
        self.vpot_values = {
            0: 0, 1: 0, 2: 0, 3: 0, 
            4: 0, 5: 0, 6: 0, 7: 0, 
            8: 0
        }


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
            self.midi_out.send_message(message.encode())
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
                # match?
                match message := message[0]:
                    case 0xF0:
                        self.receive_sysex(message)
                        continue
                    case _ if message[0] & 0xF0 == 0xE0: 
                        self.receive_fader(message)
                        continue
                    case _:
                        continue
                # ... more receives


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

    
    def receive_fader(self, message: list[int]) -> None:
        """
        Rx handler for fader change messages

        Args:
            message (list[int]): incoming raw MIDI
        """
        message_obj = FaderMoveEvent.from_midi(message)
        self.tx_queue.put_nowait(
            UpdateMeter(
                message_obj.index,
                value=0-((message_obj.position / 16380) * -60) -60
            )
        )


    def receive_button(self, message: list[int]) -> None:
        """
        Rx handler for button press/release messages

        Args:
            message (list[int]): incoming raw MIDI
        """
        raise NotImplementedError

    
    def receive_vpot(self, message: list[int]) -> None:
        """
        Rx handler for VPot change messages

        Args:
            message (list[int]): incoming raw MIDI
        """
        raise NotImplementedError


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