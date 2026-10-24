"""Simple sample for queries to the DALI bus

This example sends the query QUERY CONTROL GEAR PRESENT twice:

- to all control gears (broadcast, 0xFF91),
- to the control gear with short address 12 (0x1991).

A control gear that receives the query answers with YES, a backward frame with the value 0xFF.
So the broadcast query is answered if there is at least one control gear on the bus.
The second query is answered only if a control gear has short address 12, otherwise it times out.
If several control gears answer at the same time, their answers overlap and arrive as a corrupted frame.
This still counts as an answer.

The loop continues until it is interrupted, for example with Ctrl+C.

The interface is selected on the command line:

    python example/query.py usb                       # Lunatone DALI USB
    python example/query.py serial /dev/ttyUSB0       # SevenLab serial adapter
    python example/query.py mock                      # no hardware, every query times out
"""

import sys
import time

from dali_interface import DaliFrame, DaliInterface, DaliMock, DaliSerial, DaliStatus, DaliUsb

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
    print("Usage: python example/query.py (serial|usb|mock) [portname]")
    sys.exit()

# 16-bit forward frames: address byte, followed by the command 0x91 QUERY CONTROL GEAR PRESENT
# address byte 0xFF is broadcast, address byte 0x19 is short address 12: (12 << 1) | 1
query_broadcast = DaliFrame(length=16, data=0xFF91)
query_short_address_12 = DaliFrame(length=16, data=0x1991)


def output_result(label: str, frame: DaliFrame) -> None:
    if frame.status == DaliStatus.FRAME:
        print(f"{label}: answer 0x{frame.data:02X}")
    elif frame.status == DaliStatus.TIMEOUT:
        print(f"{label}: no answer")
    elif frame.status == DaliStatus.TIMING:
        # several control gears answered at the same time, their backward frames overlap
        print(f"{label}: corrupted answer, counts as an answer ({frame.message})")
    else:
        print(f"{label}: interface problem: {frame.status.name} ({frame.message})")


while True:
    output_result("broadcast", dali_connection.query_reply(query_broadcast))
    time.sleep(0.75)
    output_result("short address 12", dali_connection.query_reply(query_short_address_12))
    time.sleep(0.75)
