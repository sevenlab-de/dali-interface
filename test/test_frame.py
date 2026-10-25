"""
Tests for DaliFrame. They run without hardware.
"""

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
