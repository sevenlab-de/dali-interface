"""Simple sample for using the DALI interface

This example switches all control gears on the DALI bus between maximum level and off.
It sends the broadcast commands RECALL MAX LEVEL (0xFF05) and OFF (0xFF00) every 0.75 seconds.
The loop continues until it is interrupted, for example with Ctrl+C.

The interface is selected on the command line:

    python example/blinky.py usb                      # Lunatone DALI USB
    python example/blinky.py serial /dev/ttyUSB0      # SevenLab serial adapter
    python example/blinky.py mock                     # no hardware, print the commands
"""

import sys
import time

from dali_interface import DaliFrame, DaliInterface, DaliMock, DaliSerial, DaliUsb

dali_connection: DaliInterface | None = None
try:
    if sys.argv[1] == "serial":
        dali_connection = DaliSerial(sys.argv[2])
    elif sys.argv[1] == "usb":
        dali_connection = DaliUsb()
    elif sys.argv[1] == "mock":
        dali_connection = DaliMock()
except IndexError:
    pass
if not dali_connection:
    print("Usage: python example/blinky.py (serial|usb|mock) [portname]")
    sys.exit()

# 16-bit forward frames: address byte 0xFF is broadcast, followed by the command
frame_recall_max = DaliFrame(length=16, data=0xFF05)
frame_off = DaliFrame(length=16, data=0xFF00)

print("start of loop")
while True:
    dali_connection.transmit(frame_recall_max, block=True)
    time.sleep(0.75)
    dali_connection.transmit(frame_off, block=True)
    time.sleep(0.75)
