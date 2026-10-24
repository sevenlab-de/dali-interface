"""
Hardware-in-the-loop tests.

The tests need this setup:
- a Lunatone DALI USB interface,
- a SevenLab DALI serial adapter, by default at /dev/ttyDALI (see the option --serial-port),
- both connected to the same DALI bus, with a DALI bus power supply.

No control gear or control device may be connected to the bus. The tests send arbitrary
DALI commands, including broadcast configuration commands like SET SHORT ADDRESS, that change
the configuration of connected devices. Answering devices also make the tests fail.

Run the tests with `./run_hitl_local.sh`.
"""

import logging
import threading
import time

import pytest

from dali_interface import DaliFrame, DaliInterface, DaliSerial, DaliStatus, DaliUsb

logger = logging.getLogger(__name__)
general_readtimeout_for_test = 0.5
# backward frame YES, sent by reply_thread
REPLY = DaliFrame(length=8, data=0xFF)


def xfer_frame_no_block(source: DaliInterface, destination: DaliInterface, frame: DaliFrame) -> None:
    success = source.transmit(frame, block=False)
    assert success
    result = destination.get(timeout=general_readtimeout_for_test)
    loopback = source.get(timeout=general_readtimeout_for_test)
    assert result == frame
    assert result.status == DaliStatus.FRAME
    assert loopback == frame
    assert loopback.status == DaliStatus.LOOPBACK


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


def reply_thread(
    interface: DaliInterface, stop: threading.Event, request: DaliFrame | None, ready: threading.Event
) -> None:
    """
    Thread that waits for any 16bit frame, or only for `request` if given,
    and then sends the backward frame REPLY.

    The thread plays a control gear. Its answer is later than from a real control gear:
    measured from the end of the request, the serial adapter answers after about 6 to 7 ms,
    the Lunatone after about 12 ms. That is later than the 10.5 ms a transmitter may take,
    but still within the 12.4 ms in which a receiver accepts a backward frame
    (IEC 62386-101 Table 17 and Table 20). The delay comes from the round trip through the
    interface and the host.
    """
    logger.debug("reply thread started")
    interface.flush_queue()
    ready.set()
    while not stop.is_set():
        frame = interface.get(0.02)
        if frame.length == 16 and (request is None or frame == request):
            interface.transmit(REPLY, block=True)


def start_reply_thread(
    interface: DaliInterface, stop: threading.Event, request: DaliFrame | None = None
) -> threading.Thread:
    """
    Start reply_thread and wait until it is ready. It flushes the receive queue when it starts,
    so a request sent before would be lost.
    """
    ready = threading.Event()
    reply_worker = threading.Thread(target=reply_thread, args=(interface, stop, request, ready))
    reply_worker.start()
    assert ready.wait(timeout=1), "reply thread did not start"
    return reply_worker


def xfer_and_reply(source: DaliInterface, destination: DaliInterface) -> None:
    """
    Transmit a 16bit frame and read the backward frame.
    """
    stop = threading.Event()
    reply_worker = start_reply_thread(destination, stop)
    try:
        request = DaliFrame(length=16, data=0x5555)
        reply = source.query_reply(request)
        assert reply.status == DaliStatus.FRAME
        assert reply == REPLY
    finally:
        stop.set()
        reply_worker.join()


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


def keep_frame_on_blocking_transmit(source: DaliInterface, destination: DaliInterface) -> None:
    """
    Receive a frame, then transmit with `block=True`, then read the received frame.
    """
    received = DaliFrame(length=16, data=0x5555)
    sent = DaliFrame(length=16, data=0xAAAA)
    try:
        assert source.transmit(received, block=True)
        # give the reader thread of destination time to queue the frame
        time.sleep(0.05)
        assert destination.transmit(sent, block=True)
        result = destination.get(timeout=general_readtimeout_for_test)
        assert result == received, "frame received before a blocking transmit got lost"
        result = source.get(timeout=general_readtimeout_for_test)
        assert result == sent
    finally:
        source.flush_queue()
        destination.flush_queue()


def test_keep_frame_on_blocking_transmit(dali_serial: DaliSerial, dali_usb: DaliUsb) -> None:
    """
    A blocking transmit must not discard frames that were received before.
    """
    keep_frame_on_blocking_transmit(dali_serial, dali_usb)
    keep_frame_on_blocking_transmit(dali_usb, dali_serial)


def query_is_atomic(source: DaliInterface, destination: DaliInterface, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Start a blocking transmit from a second thread right after the query frame was sent.
    The second transmit must wait until query_reply has read the reply, and it must not be
    sent as a query.
    """
    request = DaliFrame(length=16, data=0x5555)
    other = DaliFrame(length=16, data=0xAAAA)
    events: list[tuple[str, DaliFrame | None, bool]] = []
    other_thread = threading.Thread(target=source.transmit, args=(other,), kwargs={"block": True})
    transmit_locked = source._transmit_locked  # pyright: ignore[reportPrivateUsage]

    def record_transmit(frame: DaliFrame, is_query: bool = False) -> None:
        events.append(("transmit", frame, is_query))
        transmit_locked(frame, is_query)
        if frame == request:
            other_thread.start()

    monkeypatch.setattr(source, "_transmit_locked", record_transmit)
    get = source.queue.get

    def record_get(block: bool = True, timeout: float | None = None) -> DaliFrame:
        # query_reply reads the reply while it still holds the transmit lock
        frame = get(block, timeout)
        events.append(("reply read", None, False))
        return frame

    monkeypatch.setattr(source.queue, "get", record_get)

    stop = threading.Event()
    reply_worker = start_reply_thread(destination, stop)
    try:
        reply = source.query_reply(request)
        other_thread.join(timeout=2)
        assert events == [
            ("transmit", request, True),
            ("reply read", None, False),
            ("transmit", other, False),
        ]
        assert reply.status == DaliStatus.FRAME
        assert reply == REPLY
    finally:
        stop.set()
        reply_worker.join()
        other_thread.join(timeout=2)
        monkeypatch.undo()
        # let late events, like the USB timeout event after a backward frame, arrive before flushing
        time.sleep(0.1)
        source.flush_queue()
        destination.flush_queue()


def test_query_is_atomic(dali_serial: DaliSerial, dali_usb: DaliUsb, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    A transmit from another thread must not interfere with a running `query_reply`.
    """
    query_is_atomic(dali_serial, dali_usb, monkeypatch)
    query_is_atomic(dali_usb, dali_serial, monkeypatch)


def test_full_queue_does_not_block_transmit(dali_serial: DaliSerial, dali_usb: DaliUsb) -> None:
    """
    Frames nobody reads must not stall the reader thread. When the receive queue is full,
    a blocking transmit must still see its loopback in time, and the newest frames are kept.
    """
    frames = [DaliFrame(length=16, data=0x5500 + i) for i in range(DaliInterface.QUEUE_SIZE + 3)]
    try:
        dali_usb.flush_queue()
        for frame in frames:
            assert dali_serial.transmit(frame, block=True)
        time.sleep(0.05)
        start = time.monotonic()
        success = dali_usb.transmit(DaliFrame(length=16, data=0xAAAA), block=True)
        duration = time.monotonic() - start
        assert success
        assert duration < 0.2, f"blocking transmit took {duration:.2f} s"
        received: list[DaliFrame] = []
        while (frame := dali_usb.get(timeout=0.05)).status != DaliStatus.TIMEOUT:
            received.append(frame)
        assert received == frames[-DaliInterface.QUEUE_SIZE :]
    finally:
        time.sleep(0.1)
        dali_serial.flush_queue()
        dali_usb.flush_queue()


def test_usb_stale_timeout_is_not_the_reply(dali_serial: DaliSerial, dali_usb: DaliUsb) -> None:
    """
    The Lunatone reports a timeout event some time after a frame without an answer.
    A query sent right after such a frame must not take that event as its reply.
    """
    request = DaliFrame(length=16, data=0x5555)
    stop = threading.Event()
    reply_worker = start_reply_thread(dali_serial, stop, request)
    try:
        for _ in range(5):
            assert dali_usb.transmit(DaliFrame(length=16, data=0xAAAA), block=True)
            reply = dali_usb.query_reply(request)
            assert reply.status == DaliStatus.FRAME, f"got {reply}"
            assert reply == REPLY
    finally:
        stop.set()
        reply_worker.join()
        time.sleep(0.1)
        dali_serial.flush_queue()
        dali_usb.flush_queue()


def test_late_reply_within_window(dali_serial: DaliSerial, dali_usb: DaliUsb) -> None:
    """
    The Python responder on the Lunatone replies about 12 ms after the request, later than a
    transmitter may (10.5 ms) but within the 12.4 ms in which a receiver accepts a backward frame
    (IEC 62386-101 Table 17 and Table 20). The serial interface must take it as the reply every time.
    """
    request = DaliFrame(length=16, data=0x5555)
    stop = threading.Event()
    reply_worker = start_reply_thread(dali_usb, stop, request)
    try:
        for _ in range(10):
            reply = dali_serial.query_reply(request)
            assert reply.status == DaliStatus.FRAME, f"got {reply}"
            assert reply == REPLY
            time.sleep(0.05)
    finally:
        stop.set()
        reply_worker.join()
        time.sleep(0.1)
        dali_serial.flush_queue()
        dali_usb.flush_queue()


def test_query_after_non_blocking_transmit(dali_serial: DaliSerial, dali_usb: DaliUsb) -> None:
    """
    The loopback of a frame transmitted without blocking arrives some time later.
    A query sent right after it must not take that loopback as its reply.
    """
    request = DaliFrame(length=16, data=0x5555)
    stop = threading.Event()
    reply_worker = start_reply_thread(dali_serial, stop, request)
    try:
        for i in range(10):
            assert dali_usb.transmit(DaliFrame(length=16, data=0x5700 + i))
            reply = dali_usb.query_reply(request)
            assert reply.status == DaliStatus.FRAME, f"got {reply}"
            assert reply == REPLY
    finally:
        stop.set()
        reply_worker.join()
        time.sleep(0.1)
        dali_serial.flush_queue()
        dali_usb.flush_queue()


def test_usb_transmit_waits_for_busy_bus(dali_serial: DaliSerial, dali_usb: DaliUsb) -> None:
    """
    The serial adapter keeps the bus busy with frames right after the stop condition, so no forward frame
    can start in between. The Lunatone holds its frame back and transmits it after the last one.
    The blocking transmit waits for it, longer than LOOPBACK_SUPERVISION_TIMEOUT, and the frames
    of the serial adapter go to the receive queue.
    """
    repetitions = 20
    try:
        dali_usb.flush_queue()
        # repeat a frame 20 times, priority 6: right after the stop condition (raw command of the serial adapter)
        dali_serial.port.write(f"R6 {repetitions:X} 10 AAAA\r".encode())
        time.sleep(0.05)
        start = time.monotonic()
        assert dali_usb.transmit(DaliFrame(length=16, data=0x5555), block=True)
        duration = time.monotonic() - start
        assert duration > DaliInterface.LOOPBACK_SUPERVISION_TIMEOUT, f"blocking transmit took {duration:.3f} s"
        frame = dali_usb.get(timeout=0)
        assert frame == DaliFrame(length=16, data=0xAAAA)
        assert frame.status == DaliStatus.FRAME
    finally:
        time.sleep(0.1)
        dali_serial.flush_queue()
        dali_usb.flush_queue()


def test_serial_transmit_behind_other_frame(dali_serial: DaliSerial, dali_usb: DaliUsb) -> None:
    """
    A frame of another bus unit is on the bus when the serial adapter gets its frame.
    The adapter reports that frame first and transmits its own frame after it.
    """
    other = DaliFrame(length=16, data=0x5555)
    try:
        for i in range(10):
            dali_serial.flush_queue()
            assert dali_usb.transmit(other)
            time.sleep(0.004 + i * 0.001)  # the frame of the Lunatone is on the bus
            assert dali_serial.transmit(DaliFrame(length=16, data=0xAAAA), block=True)
            frame = dali_serial.get(timeout=0)
            assert frame == other
            assert frame.status == DaliStatus.FRAME
            time.sleep(0.05)
            dali_usb.flush_queue()
    finally:
        time.sleep(0.1)
        dali_serial.flush_queue()
        dali_usb.flush_queue()
