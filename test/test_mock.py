"""
Tests for DaliMock. They run without hardware.
"""

import threading
import time

import pytest

from dali_interface import DaliFrame, DaliMock, DaliStatus


class DelayedLoopbackMock(DaliMock):
    """
    Mock that reports the loopback some time after the transmission, like a real interface.
    So a second frame can be transmitted before the loopback of the first one arrives.
    """

    LOOPBACK_DELAY = 0.1

    def _transmit_locked(self, frame: DaliFrame, is_query: bool = False) -> None:
        loopback = frame._replace(status=DaliStatus.LOOPBACK, message="LOOPBACK FRAME")
        reports = [loopback] * (2 if frame.send_twice else 1)
        if is_query:
            reports.append(DaliFrame(status=DaliStatus.TIMEOUT, message="mock timeout"))

        def report() -> None:
            for report_frame in reports:
                self.bus.put(report_frame._replace(timestamp=time.monotonic()))

        threading.Timer(self.LOOPBACK_DELAY, report).start()


def test_mock_blocking_transmit() -> None:
    """
    A blocking transmit returns at once and reports success.
    """
    with DaliMock() as dali_mock:
        start = time.monotonic()
        assert dali_mock.transmit(DaliFrame(length=16, data=0xFF00), block=True)
        assert time.monotonic() - start < 0.1


def test_mock_loopback() -> None:
    """
    Like a real interface, the mock reports a frame sent without blocking as loopback.
    """
    frame = DaliFrame(length=16, data=0xFF00)
    with DaliMock() as dali_mock:
        assert dali_mock.transmit(frame)
        loopback = dali_mock.get(timeout=0.5)
        assert loopback == frame
        assert loopback.status == DaliStatus.LOOPBACK


def test_mock_query_reply() -> None:
    """
    Nobody answers on the mock bus, so a query times out.
    """
    with DaliMock() as dali_mock:
        reply = dali_mock.query_reply(DaliFrame(length=16, data=0xFF91))
        assert reply.status == DaliStatus.TIMEOUT


def test_mock_blocking_transmit_waits_for_its_own_loopback() -> None:
    """
    The loopback of an earlier non-blocking transmit of the same frame must not complete
    a blocking transmit. It stays in the receive queue.
    """
    frame = DaliFrame(length=16, data=0x1234)
    with DelayedLoopbackMock() as dali_mock:
        assert dali_mock.transmit(frame)
        assert dali_mock.transmit(frame, block=True)
        loopback = dali_mock.get(timeout=0)
        assert loopback == frame
        assert loopback.status == DaliStatus.LOOPBACK
        assert dali_mock.get(timeout=0.3).status == DaliStatus.TIMEOUT


def test_mock_query_after_non_blocking_transmit_of_the_same_frame() -> None:
    """
    The loopback of an earlier non-blocking transmit of the same frame must not be taken as
    the loopback of a query, otherwise the query returns its own loopback as the reply.
    """
    request = DaliFrame(length=16, data=0xFF91)
    with DelayedLoopbackMock() as dali_mock:
        assert dali_mock.transmit(request)
        reply = dali_mock.query_reply(request)
        assert reply.status == DaliStatus.TIMEOUT, f"got {reply}"


class SilentMock(DaliMock):
    """
    Mock that reports the loopback, but neither a reply nor a timeout for a query.
    """

    def _transmit_locked(self, frame: DaliFrame, is_query: bool = False) -> None:
        self.bus.put(frame._replace(timestamp=time.monotonic(), status=DaliStatus.LOOPBACK))


def test_mock_interface_reports_nothing_after_query() -> None:
    """
    The interface must report a reply or a timeout after the reply window. If it reports nothing,
    query_reply indicates an interface failure.
    """
    with SilentMock() as dali_mock:
        start = time.monotonic()
        reply = dali_mock.query_reply(DaliFrame(length=16, data=0xFF91))
        duration = time.monotonic() - start
        assert reply.status == DaliStatus.INTERFACE
        assert DaliMock.REPLY_SUPERVISION_TIMEOUT <= duration < DaliMock.REPLY_SUPERVISION_TIMEOUT + 0.1


class LosesFirstLoopbackMock(DaliMock):
    """
    Mock that loses the loopback of the first frame, for example because of a collision.
    """

    lost = False

    def _transmit_locked(self, frame: DaliFrame, is_query: bool = False) -> None:
        if not self.lost:
            self.lost = True
            return
        super()._transmit_locked(frame, is_query)


def test_mock_retry_after_lost_loopback() -> None:
    """
    A lost loopback is an error for that transmission only. A retry of the same frame succeeds at once.
    """
    frame = DaliFrame(length=16, data=0xFF05)
    with LosesFirstLoopbackMock() as dali_mock:
        assert not dali_mock.transmit(frame, block=True)
        start = time.monotonic()
        assert dali_mock.transmit(frame, block=True)
        assert time.monotonic() - start < 0.1


class ReportsErrorMock(DaliMock):
    """
    Mock that reports an interface error instead of the loopback.
    """

    def _transmit_locked(self, frame: DaliFrame, is_query: bool = False) -> None:
        self.bus.put(DaliFrame(status=DaliStatus.INTERFACE, message="ERROR: INTERFACE"))


def test_mock_error_instead_of_loopback() -> None:
    """
    The first frame read after a transmission has to be its loopback. An error instead is reported
    as an interface error at once, not as a missing reply.
    """
    with ReportsErrorMock() as dali_mock:
        start = time.monotonic()
        reply = dali_mock.query_reply(DaliFrame(length=16, data=0xFF91))
        assert reply.status == DaliStatus.INTERFACE
        assert time.monotonic() - start < 0.1
        assert not dali_mock.transmit(DaliFrame(length=16, data=0xFF00), block=True)


class BrokenReaderMock(DaliMock):
    """
    Mock whose interface fails while reading.
    """

    def read_frame(self) -> DaliFrame | None:
        raise OSError("I/O error")


def test_mock_reader_error_raises() -> None:
    """
    After an error while reading, transmit, query_reply and get raise an error instead of reporting
    missing loopbacks or replies.
    """
    dali_mock = BrokenReaderMock()
    dali_mock.thread.join(timeout=1)
    with pytest.raises(RuntimeError):
        dali_mock.transmit(DaliFrame(length=16, data=0xFF00), block=True)
    with pytest.raises(RuntimeError):
        dali_mock.query_reply(DaliFrame(length=16, data=0xFF91))
    with pytest.raises(RuntimeError):
        dali_mock.get(timeout=0.1)


FOREIGN = DaliFrame(length=16, data=0xAAAA)


class BusyBusMock(DaliMock):
    """
    Mock on a bus that another bus unit keeps busy: the interface reports frames of the other unit
    and transmits its own frame after them, or never if `send` is False.
    """

    FOREIGN_FRAMES = 4
    FOREIGN_SPACING = 0.08
    send = True

    def _transmit_locked(self, frame: DaliFrame, is_query: bool = False) -> None:
        reports = [FOREIGN._replace(status=DaliStatus.FRAME)] * self.FOREIGN_FRAMES
        if self.send:
            reports += [frame._replace(status=DaliStatus.LOOPBACK)] * (2 if frame.send_twice else 1)
            if is_query:
                reports.append(DaliFrame(status=DaliStatus.TIMEOUT, message="mock timeout"))

        def report() -> None:
            for report_frame in reports:
                time.sleep(self.FOREIGN_SPACING)
                self.bus.put(report_frame._replace(timestamp=time.monotonic()))

        threading.Thread(target=report, daemon=True).start()


def test_mock_transmit_waits_for_busy_bus() -> None:
    """
    While other bus units transmit, the interface holds the frame back. A blocking transmit waits
    beyond LOOPBACK_SUPERVISION_TIMEOUT as long as frames are reported, and the frames go to the receive queue.
    """
    with BusyBusMock() as dali_mock:
        assert BusyBusMock.FOREIGN_FRAMES * BusyBusMock.FOREIGN_SPACING > DaliMock.LOOPBACK_SUPERVISION_TIMEOUT
        start = time.monotonic()
        assert dali_mock.transmit(DaliFrame(length=16, data=0xFF00, send_twice=True), block=True)
        assert time.monotonic() - start >= BusyBusMock.FOREIGN_FRAMES * BusyBusMock.FOREIGN_SPACING
        for _ in range(BusyBusMock.FOREIGN_FRAMES):
            frame = dali_mock.get(timeout=0)
            assert frame == FOREIGN
            assert frame.status == DaliStatus.FRAME
        assert dali_mock.get(timeout=0).status == DaliStatus.TIMEOUT


def test_mock_query_on_busy_bus() -> None:
    """
    Frames of other bus units before the loopback of the request are not the reply.
    """
    with BusyBusMock() as dali_mock:
        reply = dali_mock.query_reply(DaliFrame(length=16, data=0xFF91))
        assert reply.status == DaliStatus.TIMEOUT, f"got {reply}"


def test_mock_no_loopback_after_busy_bus() -> None:
    """
    If the interface reports nothing for LOOPBACK_SUPERVISION_TIMEOUT after the last frame of
    another bus unit, the transmission failed.
    """
    with BusyBusMock() as dali_mock:
        dali_mock.send = False
        start = time.monotonic()
        assert not dali_mock.transmit(DaliFrame(length=16, data=0xFF00), block=True)
        expected = BusyBusMock.FOREIGN_FRAMES * BusyBusMock.FOREIGN_SPACING + DaliMock.LOOPBACK_SUPERVISION_TIMEOUT
        assert expected <= time.monotonic() - start < expected + 0.1


class ReaderFailsLaterMock(DaliMock):
    """
    Mock that reports no loopback, and whose interface fails while reading after some time.
    """

    FAIL_AFTER = 0.1

    def __init__(self) -> None:
        self.fail_at = time.monotonic() + self.FAIL_AFTER
        super().__init__()

    def _transmit_locked(self, frame: DaliFrame, is_query: bool = False) -> None:
        pass

    def read_frame(self) -> DaliFrame | None:
        time.sleep(0.01)
        if time.monotonic() >= self.fail_at:
            raise OSError("I/O error")
        return None


def test_mock_reader_fails_while_waiting_for_previous_loopback() -> None:
    """
    A transmit waits for the loopback of the previous frame. If the reader fails meanwhile,
    the transmit raises an error instead of transmitting without a working reader.
    """
    dali_mock = ReaderFailsLaterMock()
    assert dali_mock.transmit(DaliFrame(length=16, data=0xFF00))
    with pytest.raises(RuntimeError):
        dali_mock.transmit(DaliFrame(length=16, data=0xFF01))


class ReaderFailsAfterTransmitMock(DaliMock):
    """
    Mock whose interface fails while reading after a transmission, before reporting the loopback or the reply.
    `loopback` selects whether the loopback is reported before the failure.
    """

    loopback = False
    fail = False

    def _transmit_locked(self, frame: DaliFrame, is_query: bool = False) -> None:
        if self.loopback:
            self.bus.put(frame._replace(timestamp=time.monotonic(), status=DaliStatus.LOOPBACK))
        self.fail = True

    def read_frame(self) -> DaliFrame | None:
        if not self.bus.empty():
            return self.bus.get_nowait()
        if self.fail:
            time.sleep(0.05)
            raise OSError("I/O error")
        time.sleep(0.01)
        return None


def test_mock_reader_fails_while_waiting_for_loopback() -> None:
    """
    If the reader fails while a blocking transmit or a query waits for the loopback, they raise an error.
    """
    with pytest.raises(RuntimeError):
        ReaderFailsAfterTransmitMock().transmit(DaliFrame(length=16, data=0xFF00), block=True)
    with pytest.raises(RuntimeError):
        ReaderFailsAfterTransmitMock().query_reply(DaliFrame(length=16, data=0xFF91))


def test_mock_reader_fails_while_waiting_for_reply() -> None:
    """
    If the reader fails while a query waits for the reply, the query raises an error.
    """
    dali_mock = ReaderFailsAfterTransmitMock()
    dali_mock.loopback = True
    with pytest.raises(RuntimeError):
        dali_mock.query_reply(DaliFrame(length=16, data=0xFF91))
