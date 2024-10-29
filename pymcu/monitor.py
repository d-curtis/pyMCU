import rtmidi
import asyncio

from rtmidi.midiutil import open_midiinput, open_midioutput

from messages import *

PING_INTERVAL = 1

response_queue = asyncio.Queue()

def handle_message(message: MCUBase):
    print(f"Rx: {message}")
    
    if message.response_required:
        response_queue.put_nowait(message)

    
async def responder(midi_out: rtmidi.MidiOut):
    while True:
        message = await response_queue.get()

        match message:
            case message if type(message) == HostConnectionQuery:
                reply = HostConnectionReply(
                    serial_number=message.serial_number, 
                    challenge_code=message.challenge_code
                )
                print(f"Tx: {reply}")
                midi_out.send_message(reply.to_syx())

                midi_out.send_message(UpdateLCD(text="Hello, World!").to_syx())

                for i, c in enumerate("Hi Connor"):
                    midi_out.send_message(
                        UpdateTimecodeChar(
                            char=c, 
                            display_offset=i, 
                            left_to_right=True
                        ).to_syx()
                    )

        response_queue.task_done()


async def handle_midi_input(midi_in: rtmidi.MidiIn, midi_out: rtmidi.MidiOut):
    """Listen for incoming MIDI messages."""
    while True:
        message = midi_in.get_message()  # Get the message
        if message:
            message, _ = message
            if message[0] == 0xF0:
                if message[5] in MESSAGE_CLASSES:
                    handle_message(MESSAGE_CLASSES[message[5]].from_syx(message))
                else:
                    print(f"Rx (Unknown Syx): {hex_string(message)}")
            elif message[0] in range(0xE0, 0xEF):
                print(f"Rx (Fader): {hex_string(message)}")
                midi_out.send_message(message)
            else:
                print(f"Rx (Unknown): {hex_string(message)}")
        await asyncio.sleep(0.01)  # Allow other tasks to run


async def send_ping(midi_out: rtmidi.MidiOut):
    """Send a PING message."""
    while True:
        print(f"Tx: {DeviceQuery()}")
        midi_out.send_message(DeviceQuery().to_syx())
        await asyncio.sleep(PING_INTERVAL)  # Wait a moment before exiting


def main():
    input_device_name = "X-Touch INT"  # Replace with your actual input device name
    output_device_name = "X-Touch INT"  # Replace with your actual output device name

    midi_in, _ = open_midiinput(input_device_name)
    midi_out, _ = open_midioutput(output_device_name)

    midi_in.ignore_types(False, False, False)

    # Create the asyncio event loop
    loop = asyncio.get_event_loop()
    tasks = [
        handle_midi_input(midi_in, midi_out),
        send_ping(midi_out),
        responder(midi_out)
    ]
    loop.run_until_complete(asyncio.gather(*tasks))

if __name__ == '__main__':
    main()