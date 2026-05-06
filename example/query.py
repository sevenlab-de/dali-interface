"""Simple sample for queries to the DALI bus

This code queries control gears connected to the interface's DALI bus. The expected result is a YES backframe (0xFF)
for the broadcast query (0xFF91). If no control gear on the bus has the short address 12 assigned, the second query
will result in a timeout.

"""

from dali_interface import DaliInterface, DaliSerial, DaliUsb, DaliMock, DaliFrame, DaliStatus
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
    print("Usage: python query.py (serial|usb|mock) [portname]")
    exit()

frame_query_success = DaliFrame(length=16, data=0xFF91)
frame_query_timeout = DaliFrame(length=16, data=0x1991)


def output_result(frame: DaliFrame) -> None:
    if frame.status == DaliStatus.FRAME:
        print(f"valid frame: {frame.data:02X}")
    elif frame.status == DaliStatus.TIMEOUT:
        print("timeout received")
    else:
        print("unexpected result")


while True:
    result = dali_connection.query_reply(frame_query_success)
    output_result(result)
    time.sleep(0.75)
    result = dali_connection.query_reply(frame_query_timeout)
    output_result(result)
    time.sleep(0.75)
