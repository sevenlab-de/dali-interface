"""Simple sample for using the DALI interface

This code makes all control gears connected to the interface's DALI bus change between off and maximum
intensity. The loop continues until it is externally interrupted.

"""

from dali_interface import DaliInterface, DaliSerial, DaliUsb, DaliMock, DaliFrame
import time
import sys

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
    print("Usage: python blinky.py (serial|usb|mock) [portname]")
    exit()

frame_recall_max = DaliFrame(length=16, data=0xFF05)
frame_off = DaliFrame(length=16, data=0xFF00)

print("start of loop")
while True:
    dali_connection.transmit(frame_recall_max, block=True)
    time.sleep(0.75)
    dali_connection.transmit(frame_off, block=True)
    time.sleep(0.75)
