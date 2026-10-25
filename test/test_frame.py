"""
Tests for DaliFrame. They run without hardware.
"""

import pytest

from dali_interface import DaliFrame, DaliStatus


def test_frames_with_same_length_and_data_are_equal() -> None:
    """
    Frames are compared by length and data only, the other fields are ignored.
    """
    frame = DaliFrame(length=16, data=0x1234)
    other = DaliFrame(timestamp=1.0, length=16, data=0x1234, status=DaliStatus.LOOPBACK, message="LOOPBACK")
    assert frame == other
    assert hash(frame) == hash(other)
    assert frame != DaliFrame(length=24, data=0x1234)
    assert frame != DaliFrame(length=16, data=0x1235)


def test_frame_is_not_equal_to_a_tuple() -> None:
    """
    A frame is not equal to a plain tuple with the same fields, otherwise equal values would have different hashes.
    """
    frame = DaliFrame(length=16, data=0x1234)
    values = tuple(frame)
    assert frame != values
    assert values != frame
    assert values not in {frame}


def test_bytes_of_a_16_bit_frame() -> None:
    """
    A 16 bit forward frame consists of the address byte and the opcode byte.
    """
    frame = DaliFrame(length=16, data=0xA315)
    assert frame.address_byte == 0xA3
    assert frame.opcode_byte == 0x15
    assert frame.number_nibble == 0x05
    with pytest.raises(ValueError):
        _ = frame.instance_byte


def test_bytes_of_a_24_bit_frame() -> None:
    """
    A 24 bit forward frame consists of the address byte, the instance byte and the opcode byte.
    """
    frame = DaliFrame(length=24, data=0xC1FE2B)
    assert frame.address_byte == 0xC1
    assert frame.instance_byte == 0xFE
    assert frame.opcode_byte == 0x2B
    assert frame.number_nibble == 0x0B


@pytest.mark.parametrize("length", [0, 8, 17, 25, 32])
def test_bytes_of_other_frames(length: int) -> None:
    """
    Other frames, like a backward frame, have no address, instance or opcode byte.
    """
    frame = DaliFrame(length=length, data=0xFF)
    for name in ("address_byte", "instance_byte", "opcode_byte", "number_nibble"):
        with pytest.raises(ValueError):
            getattr(frame, name)
