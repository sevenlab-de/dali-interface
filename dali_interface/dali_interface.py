"""Define the base classes exposed by DALI-interface"""

from __future__ import annotations

import logging
import queue
import threading
import time
from types import TracebackType


from .frame import DaliStatus, DaliFrame

logger = logging.getLogger(__name__)


class DaliInterface:
    """Abstract DALI interface class."""

    RECEIVE_TIMEOUT = 1
    QUEUE_SIZE = 5
    SLEEP_FOR_THREAD_END = 0.001
    DALI_BAUD = 1200

    def __init__(self) -> None:
        """Initialize DALI interface."""
        self.queue: queue.Queue[DaliFrame] = queue.Queue(maxsize=self.QUEUE_SIZE)
        self.keep_running = False
        self.expected_response: DaliFrame | None = None
        self.expected_response_event: threading.Event = threading.Event()
        self.expected_twice = False
        self.transmit_lock: threading.Lock = threading.Lock()
        self.next_frame_not_earlier_than: float = 0.0
        self.expect_reply = False
        self.reply_timeout = 0.2
        self._start_receive()

    def __enter__(self) -> DaliInterface:
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

    def _read_worker_thread(self) -> None:
        """The read thread which is executed to read DALI frames from the interface."""
        logger.debug("read_worker_thread started")
        while self.keep_running:
            try:
                frame = self.read_frame()
                if frame is None:
                    continue
                logger.debug(f"received: {frame}")
                if frame == self.expected_response:
                    if self.expected_twice:
                        self.expected_twice = False
                    else:
                        self.expected_response = None
                        self.expected_response_event.set()
                else:
                    if self.expect_reply or frame.status != DaliStatus.TIMEOUT:
                        self.queue.put(frame, timeout=self.RECEIVE_TIMEOUT)
            except queue.Full:
                logger.warning("receive queue full, dropping frame")
                pass
            except NotImplementedError:
                logger.warning("no valid read_frame implementation, terminate read_worker_thread")
                self.keep_running = False
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
        """
        logger.debug("get")
        if not self.keep_running:
            raise Exception("read thread is not running")
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

    def transmit(self, frame: DaliFrame, block: bool = False) -> bool:
        """Transmit a DALI frame. All 8 bit frames are treated as backward frames.

        Args:
            frame (DaliFrame): frame to transmit
            block (bool, optional): wait for the end of transmission.
                Defaults to False.

        Returns:
            True: successful transmission
            False: timeout while waiting for loopback
        """
        with self.transmit_lock:
            logger.debug("lock acquired - start transmission")
            now = time.monotonic()
            if now < self.next_frame_not_earlier_than:
                logger.debug(f"need to sleep for {self.next_frame_not_earlier_than - now} sec")
                time.sleep(self.next_frame_not_earlier_than - now)

            if block:
                self.flush_queue()
                self.expected_response_event.clear()
                self.expected_response = frame
                self.expected_twice = frame.send_twice

            try:
                self._transmit_locked(frame, self.expect_reply)
                self.next_frame_not_earlier_than = time.monotonic() + ((frame.length + 1) / self.DALI_BAUD)

                if block:
                    return self.expected_response_event.wait(timeout=self.RECEIVE_TIMEOUT)
                else:
                    return True
            finally:
                self.expected_response = None

    def query_reply(self, request: DaliFrame) -> DaliFrame:
        """Transmit a DALI frame that is requesting a reply. Wait for either
            the replied data, or indicate a timeout.

        Args:
            request (DaliFrame): frame to transmit

        Returns:
            DaliFrame: the received reply, if no reply was received a frame with DaliStatus:TIMEOUT is returned
        """
        try:
            self.expect_reply = True
            success = self.transmit(request, block=True)
            if not success:
                raise TimeoutError("transmit timed out waiting for loopback")
            logger.debug("read backframe")
            result = self.get(timeout=self.reply_timeout)
        finally:
            self.expect_reply = False
        return result

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
