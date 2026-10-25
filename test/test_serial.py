"""
Tests for parsing the messages of the serial adapter. They run without hardware.
"""

import pytest

from dali_interface import DaliSerial, DaliStatus


@pytest.mark.parametrize(
    "line, status",
    [
        ("{00001234:10 0000FF00}", DaliStatus.FRAME),
        ("{00001234>10 0000FF00}", DaliStatus.LOOPBACK),
        ("{00001234:81 00000000}", DaliStatus.TIMEOUT),
        ("{00001234:82 00012305}", DaliStatus.TIMING),
        ("{00001234:83 00012305}", DaliStatus.TIMING),
        ("{00001234:88 00000000}", DaliStatus.TIMING),
        ("{00001234:91 00000000}", DaliStatus.FAILURE),
        ("{00001234:92 00271000}", DaliStatus.RECOVER),
        ("{00001234:A0 00000000}", DaliStatus.INTERFACE),
        ("{00001234:A2 00000000}", DaliStatus.INTERFACE),
        ("{00001234:A3 00000000}", DaliStatus.INTERFACE),
        ("{00001234:A5 00000000}", DaliStatus.INTERFACE),
        # codes no longer used
        ("{00001234:84 00000000}", DaliStatus.INTERFACE),
    ],
)
def test_parse_status(line: str, status: DaliStatus) -> None:
    """
    Each message of the serial adapter maps to its status.
    """
    frame = DaliSerial.parse(line)
    assert frame is not None
    assert frame.status == status
