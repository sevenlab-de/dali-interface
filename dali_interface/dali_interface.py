"""Define the base classes exposed by DALI-interface"""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from types import TracebackType
from typing import TYPE_CHECKING

from .frame import DaliFrame, DaliStatus

if TYPE_CHECKING:
    from typing_extensions import Self

logger = logging.getLogger(__name__)


@dataclass
class _InFlight:
    """The transmitted frame whose loopback has not been read yet."""

    frame: DaliFrame
    count: int  # number of loopbacks still expected, 2 for send-twice frames
    block: bool  # a blocking transmit consumes the loopback, otherwise it goes to the receive queue
    is_query: bool  # the frame is the request of a query
    done: threading.Event = field(default_factory=threading.Event)
    error: DaliFrame | None = None  # what was read instead of the loopback
    last_activity: float = field(default_factory=time.monotonic)  # last report of the interface on the bus


class DaliInterface:
    """Abstract DALI interface class."""

    QUEUE_SIZE = 5
    SLEEP_FOR_THREAD_END = 0.001
    DALI_BAUD = 1200

    # Reply timing of IEC 62386-101. The interfaces apply it as DALI receivers and report either the
    # backward frame or a timeout; the host only checks that the interface reports in time.
    # A backward frame starts at most 12.4 ms after the forward frame, with a grey area up to 13.4 ms
    # (Table 20, 8.2.5).
    BACKWARD_FRAME_LATEST_START = 0.0134
    # start bit and 8 data bits, followed by the stop condition (Table 18)
    BACKWARD_FRAME_DURATION = 9 / DALI_BAUD + 0.0024
    # time for a command to reach the interface and for the interface to report a frame or event
    # to the host, including delays on a loaded host.
    # Not part of the standard, it does not change the reply window applied by the interface.
    INTERFACE_REPORT_LATENCY = 0.1
    # if the interface reports neither a backward frame nor a timeout within this time after
    # the loopback of the request, the interface failed
    REPLY_SUPERVISION_TIMEOUT = BACKWARD_FRAME_LATEST_START + BACKWARD_FRAME_DURATION + INTERFACE_REPORT_LATENCY
    # A forward frame starts at most at the settling time of priority 5 after the last frame on the bus
    # (Table 22).
    FORWARD_FRAME_LATEST_START = 0.0211
    # start bit and up to 32 data bits, followed by the stop condition
    FORWARD_FRAME_DURATION = 33 / DALI_BAUD + 0.0024
    # if the interface reports neither the loopback nor another frame on the bus within this time,
    # the interface failed
    LOOPBACK_SUPERVISION_TIMEOUT = FORWARD_FRAME_LATEST_START + FORWARD_FRAME_DURATION + INTERFACE_REPORT_LATENCY

    def __init__(self) -> None:
        """Initialize DALI interface."""
        self.queue: queue.Queue[DaliFrame] = queue.Queue(maxsize=self.QUEUE_SIZE)
        self.keep_running = False
        # The loopback is instantaneous on the DALI bus, only the communication with the interface
        # and frames of other bus units delay it. So only one frame is in flight: the next frame is
        # transmitted after the loopback of the previous one was read.
        self.in_flight: _InFlight | None = None
        self.read_error: BaseException | None = None
        self.transmit_lock: threading.RLock = threading.RLock()
        self.expect_reply = False
        self._start_receive()

    def __enter__(self) -> Self:
        """Access object via context manager"""
        return self

    def __exit__(
        self,
        exc_type_: type[BaseException] | None,
        exc_val: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close object via context manager"""
        self.close()

    def power(self, power: bool = False) -> None:
        """Stub for controlling a built-in power supply."""
        raise RuntimeError("subclass must implement power")

    def read_frame(self) -> DaliFrame | None:
        """Stub for reading data needs to be overwritten by an implementation."""
        raise NotImplementedError("subclass must implement read_frame")

    def flush_queue(self) -> None:
        """Flush the queue with DALI frames."""
        logger.debug("flush receive queue")
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except queue.Empty:
                continue
            self.queue.task_done()

    def _enqueue(self, frame: DaliFrame) -> None:
        """Put a frame into the queue without blocking. If the queue is full, drop the oldest frame."""
        while True:
            try:
                self.queue.put_nowait(frame)
                return
            except queue.Full:
                try:
                    dropped = self.queue.get_nowait()
                except queue.Empty:
                    continue
                self.queue.task_done()
                logger.warning(f"receive queue full, dropping oldest frame {dropped}")

    def _check_loopback(self, frame: DaliFrame) -> bool:
        """Check a received frame against the frame in flight.

        After a transmission, the interface reports its loopback, possibly after frames of other bus units.
        Those frames go to the receive queue. Anything else instead of the loopback is an error.
        Timeout events are no frames on the bus, they report the end of the reply window of
        the previous frame.

        Ideally, a frame of another bus unit would abort the transmission, so the application could
        react to it first. Neither interface can do that: both keep the frame and transmit it once
        the bus is idle for the settling time. As a workaround, the frames of other bus units are
        passed on and the supervision of the loopback starts again with each of them.

        Returns:
            True if the frame was consumed as loopback of a blocking transmit.
        """
        in_flight = self.in_flight
        if in_flight is None or frame.status == DaliStatus.TIMEOUT:
            return False
        if frame.status in (DaliStatus.FRAME, DaliStatus.TIMING):
            # another bus unit holds the bus, the interface transmits after it
            in_flight.last_activity = time.monotonic()
            return False
        if frame.status != DaliStatus.LOOPBACK or frame != in_flight.frame:
            logger.error(f"expected the loopback of {in_flight.frame}, received {frame}")
            in_flight.error = frame
            self.in_flight = None
            in_flight.done.set()
            return False
        in_flight.count -= 1
        in_flight.last_activity = time.monotonic()
        if in_flight.count == 0:
            self.in_flight = None
            if in_flight.is_query:
                # frames received before the request cannot be its reply
                self.flush_queue()
            in_flight.done.set()
        return in_flight.block

    def _read_worker_thread(self) -> None:
        """The read thread which is executed to read DALI frames from the interface."""
        logger.debug("read_worker_thread started")
        while self.keep_running:
            try:
                frame = self.read_frame()
            except Exception as error:  # noqa: BLE001 - any error stops the receive thread, see read_error
                logger.error(f"reading from the interface failed, receive thread stops: {error!r}")
                self.read_error = error
                self.keep_running = False
                in_flight = self.in_flight
                if in_flight is not None:
                    self.in_flight = None
                    in_flight.done.set()
                break
            if frame is None:
                continue
            logger.debug(f"received: {frame}")
            if self._check_loopback(frame):
                continue
            if self.expect_reply or frame.status != DaliStatus.TIMEOUT:
                self._enqueue(frame)
        logger.debug("read_worker_thread terminated")

    def _start_receive(self) -> None:
        """Start the receive thread which fills the queue with DALI frames."""
        if not self.keep_running:
            logger.debug("start receive")
            self.keep_running = True
            self.thread = threading.Thread(target=self._read_worker_thread, args=())
            self.thread.daemon = True
            self.thread.start()
            self.flush_queue()

    def get(self, timeout: float | None = None) -> DaliFrame:
        """Get the next DALI frame from the interface. Function blocks until a frame
            is received or timeout occurs.

        Args:
            timeout (float | None, optional): time in seconds before the call returns.
            Defaults to None (never timer out).

        Returns:
            DaliFrame: time out is indicated in the frame status.

        All frames go through one receive queue. While `query_reply` runs in another thread,
        a call of `get` can take the reply, and `query_reply` then reports an interface error.
        """
        logger.debug("get")
        self._check_receiving()
        try:
            rx_frame = self.queue.get(block=True, timeout=timeout)
        except queue.Empty:
            return DaliFrame(status=DaliStatus.TIMEOUT, message="queue is empty, timeout from get")
        return rx_frame

    def _transmit_locked(self, frame: DaliFrame, is_query: bool = False) -> None:
        """Raw transmission of a DALI frame, without flow control.
           All 8 bit frames are treated as backward frames.

        Args:
            frame (DaliFrame): frame to transmit
            is_query (bool, optional): The serial interface can use the query feature to always generate an answer frame.
                Defaults to False.
        """
        raise NotImplementedError("subclass must implement _transmit_locked")

    def _check_receiving(self) -> None:
        """Raise an error if the receive thread does not run."""
        if not self.keep_running:
            raise RuntimeError("read thread is not running") from self.read_error

    def _wait_for_loopback(self, in_flight: _InFlight) -> bool:
        """Wait for the loopback of the frame in flight.

        Returns:
            False if the interface reported nothing on the bus for LOOPBACK_SUPERVISION_TIMEOUT.
        """
        while True:
            deadline = in_flight.last_activity + self.LOOPBACK_SUPERVISION_TIMEOUT
            if in_flight.done.wait(timeout=max(deadline - time.monotonic(), 0)):
                return True
            if time.monotonic() >= in_flight.last_activity + self.LOOPBACK_SUPERVISION_TIMEOUT:
                return False

    def _send(self, frame: DaliFrame, block: bool) -> DaliFrame | None:
        """Transmit a frame after the loopback of the previous frame was read.

        Returns:
            None if the frame was transmitted (and, with block, its loopback was read),
            otherwise a frame with DaliStatus.INTERFACE that describes the error.
        """
        with self.transmit_lock:
            self._check_receiving()
            previous = self.in_flight
            if previous is not None and not self._wait_for_loopback(previous):
                logger.error(f"no loopback of {previous.frame}")
                self.in_flight = None
            # the receive thread can have stopped while waiting
            self._check_receiving()
            in_flight = _InFlight(
                frame=frame, count=2 if frame.send_twice else 1, block=block, is_query=self.expect_reply
            )
            # register before transmitting, the loopback can be read before _transmit_locked returns
            self.in_flight = in_flight
            try:
                self._transmit_locked(frame, self.expect_reply)
            except BaseException:
                self.in_flight = None
                raise
            if not block:
                return None
            loopback_received = self._wait_for_loopback(in_flight)
            # the receive thread can have stopped while waiting
            self._check_receiving()
            if not loopback_received:
                self.in_flight = None
                message = f"no loopback of {frame}"
            elif in_flight.error is not None:
                message = f"received {in_flight.error} instead of the loopback of {frame}"
            else:
                return None
            logger.error(message)
            return DaliFrame(timestamp=time.monotonic(), status=DaliStatus.INTERFACE, message=message)

    def transmit(self, frame: DaliFrame, block: bool = False) -> bool:
        """Transmit a DALI frame. All 8 bit frames are treated as backward frames.

        The frame is transmitted after the loopback of the previous frame was read. If other bus units
        transmit, the interface sends the frame after them, and their frames go to the receive queue.

        Args:
            frame (DaliFrame): frame to transmit
            block (bool, optional): wait for the loopback and consume it. Without block,
                the loopback goes to the receive queue. Defaults to False.

        Returns:
            True: successful transmission
            False: with block, the interface reported neither the loopback nor another frame on the bus
                within LOOPBACK_SUPERVISION_TIMEOUT, or it reported an error instead of the loopback.

        Raises:
            RuntimeError: the receive thread does not run.
        """
        return self._send(frame, block) is None

    def query_reply(self, request: DaliFrame) -> DaliFrame:
        """Transmit a DALI frame that is requesting a reply. Wait for either
            the replied data, or indicate a timeout.

        Args:
            request (DaliFrame): frame to transmit

        Returns:
            DaliFrame: the reply as reported by the interface:
                DaliStatus.FRAME: the backward frame.
                DaliStatus.TIMING: a corrupted backward frame. If several bus units reply at the same time,
                    their backward frames overlap. According to IEC 62386-101 8.2.5 such a frame still counts
                    as a backward frame, for example a YES from several control gears.
                DaliStatus.TIMEOUT: no backward frame within the reply window of IEC 62386-101.
                DaliStatus.INTERFACE: the loopback of the request was not read (see transmit), the interface
                    reported an error, or it reported neither a reply nor a timeout within REPLY_SUPERVISION_TIMEOUT.

        The reply window is defined by IEC 62386-101 and applied by the interface, which acts as the DALI
        receiver. It is not configurable.

        Frames received before the loopback of the request, from other bus units too, are discarded,
        as they cannot be the reply. The transmit lock is held until the reply is read,
        so no other frame is transmitted between the request and its reply.
        Do not call `get` from another thread meanwhile, it reads the same queue and can take the reply.

        Raises:
            RuntimeError: the receive thread does not run.
        """
        with self.transmit_lock:
            try:
                self.expect_reply = True
                error = self._send(request, block=True)
                if error is not None:
                    return error
                logger.debug("read backframe")
                try:
                    return self.queue.get(timeout=self.REPLY_SUPERVISION_TIMEOUT)
                except queue.Empty:
                    self._check_receiving()
                    logger.error("interface reported neither a reply nor a timeout")
                    return DaliFrame(
                        timestamp=time.monotonic(),
                        status=DaliStatus.INTERFACE,
                        message="interface reported neither a reply nor a timeout",
                    )
            finally:
                self.expect_reply = False

    def close(self) -> None:
        """Close the connection."""
        logger.debug("tear down connection")
        if not self.keep_running:
            logger.debug("read thread is not running")
            return
        self.keep_running = False
        while self.thread.is_alive():
            time.sleep(DaliInterface.SLEEP_FOR_THREAD_END)
        logger.debug("connection closed, thread terminated")
