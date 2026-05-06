import logging
import threading

import pytest

from dali_interface import DaliInterface, DaliStatus, DaliFrame, DaliSerial, DaliUsb


logger = logging.getLogger(__name__)
general_readtimeout_for_test = 0.5

"""
Testing assumes the following units are connected to the test runner:
DALI USB Lunatone connector
DALI/serial adapter connected to /dev/ttyDALI

A DALI power supply to both DALI bus connectors.
"""


def xfer_frame_no_block(source: DaliInterface, destination: DaliInterface, frame: DaliFrame) -> None:
    success = source.transmit(frame, block=False)
    assert success
    result = destination.get(timeout=general_readtimeout_for_test)
    loopback = source.get(timeout=general_readtimeout_for_test)
    assert result == frame
    assert loopback == frame


def xfer_frame_block(source: DaliInterface, destination: DaliInterface, frame: DaliFrame) -> None:
    success = source.transmit(frame, block=True)
    assert success
    result = destination.get(timeout=general_readtimeout_for_test)
    assert result == frame


@pytest.mark.parametrize(
    "length, data",
    [
        (
            16,
            0x0000,
        ),
        (
            16,
            0x5555,
        ),
        (
            16,
            0xAAAA,
        ),
        (
            16,
            0xFFFF,
        ),
        (
            24,
            0x000000,
        ),
        (
            24,
            0x0000FF,
        ),
        (
            24,
            0x00FF00,
        ),
        (
            24,
            0xFF0000,
        ),
        (
            24,
            0x555555,
        ),
        (
            24,
            0xAAAAAA,
        ),
        (
            24,
            0xFFFFFF,
        ),
    ],
)
def test_frame(dali_serial: DaliSerial, dali_usb: DaliUsb, length: int, data: int) -> None:
    """
    Transfer frames in between DALI connectors
    """
    frame = DaliFrame(length=length, data=data)
    xfer_frame_no_block(dali_serial, dali_usb, frame)
    xfer_frame_no_block(dali_usb, dali_serial, frame)
    xfer_frame_block(dali_serial, dali_usb, frame)
    xfer_frame_block(dali_usb, dali_serial, frame)


def test_serial_timeout(dali_serial: DaliSerial) -> None:
    """
    Try to read a reply via DALI serial adapter
    Expect a timeout as nobody answers
    """
    frame = DaliFrame(length=16, data=0x0000)
    reply = dali_serial.query_reply(frame)
    assert reply.status == DaliStatus.TIMEOUT


def test_usb_timeout(dali_usb: DaliUsb) -> None:
    """
    Try to read a reply via DALI usb adapter
    Expect a timeout as nobody answers
    """
    frame = DaliFrame(length=16, data=0x0000)
    reply = dali_usb.query_reply(frame)
    assert reply.status == DaliStatus.TIMEOUT


def reply_thread(interface: DaliInterface) -> None:
    """
    Thread that waits for any 16bit frame and
    then sends a 0xFF backward frame.
    """
    logger.debug("reply thread started")
    myself = threading.current_thread()
    reply = DaliFrame(length=8, data=0xFF)
    interface.flush_queue()
    while getattr(myself, "running", True):
        frame = interface.get(0.02)
        if frame.length == 16:
            interface.transmit(reply, block=True)


def xfer_and_reply(source: DaliInterface, destination: DaliInterface) -> None:
    """
    Transmit a 16bit frame and read the backward frame.
    """
    reply_worker = threading.Thread(target=reply_thread, args=(destination,))
    reply_worker.daemon = True
    reply_worker.start()
    request = DaliFrame(length=16, data=0x5555)
    reply = source.query_reply(request)
    assert reply.status == DaliStatus.FRAME
    assert reply.length == 8
    assert reply.data == 0xFF
    setattr(reply_worker, "running", False)


def test_query(dali_serial: DaliSerial, dali_usb: DaliUsb) -> None:
    """
    Test the `query_reply` function.
    """
    xfer_and_reply(dali_usb, dali_serial)
    xfer_and_reply(dali_serial, dali_usb)


def xfer_twice_block(source: DaliInterface, destination: DaliInterface, frame: DaliFrame) -> None:
    """
    Use transmit with a frame that has `send_twice = True` and receive the frames.
    """
    success = source.transmit(frame, block=True)
    assert success
    result = destination.get(general_readtimeout_for_test)
    assert result == frame
    result = destination.get(general_readtimeout_for_test)
    assert result == frame


@pytest.mark.parametrize(
    "length, data",
    [
        (
            16,
            0x0000,
        ),
        (
            16,
            0x5555,
        ),
        (
            16,
            0xAAAA,
        ),
        (
            16,
            0xFFFF,
        ),
        (
            16,
            0xFF80,
        ),
        (
            24,
            0x000000,
        ),
        (
            24,
            0x0000FF,
        ),
        (
            24,
            0x00FF00,
        ),
        (
            24,
            0xFF0000,
        ),
        (
            24,
            0x555555,
        ),
        (
            24,
            0xAAAAAA,
        ),
        (
            24,
            0xFFFFFF,
        ),
        (
            24,
            0xFFFF67,
        ),
    ],
)
def test_transfer_twice(dali_serial: DaliSerial, dali_usb: DaliUsb, length: int, data: int) -> None:
    """
    Transfer send twice frames in between DALI connectors
    """
    frame = DaliFrame(length=length, data=data, send_twice=True)
    xfer_twice_block(dali_serial, dali_usb, frame)
    xfer_twice_block(dali_usb, dali_serial, frame)
