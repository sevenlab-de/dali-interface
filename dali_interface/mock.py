"""Mock DALI interface for testing."""

import logging
import queue
import time

from .dali_interface import DaliInterface
from .frame import DaliFrame, DaliStatus

logger = logging.getLogger(__name__)


class DaliMock(DaliInterface):
    """Mock class for DALI interface.

    Transmitted frames are printed and reported back as loopback, like a real interface does.
    Nobody answers on the mock bus, so a query is followed by a timeout.
    """

    READ_TIMEOUT = 0.1

    def __init__(self) -> None:
        """Initialize the mock DALI interface."""
        self.bus: queue.Queue[DaliFrame] = queue.Queue()
        super().__init__()

    def _transmit_locked(self, frame: DaliFrame, is_query: bool = False) -> None:
        """Mock transmission of DALI frame."""
        print(f"{'query' if is_query else 'transmit'} {frame!r}")
        loopback = frame._replace(timestamp=time.monotonic(), status=DaliStatus.LOOPBACK, message="LOOPBACK FRAME")
        self.bus.put(loopback)
        if frame.send_twice:
            self.bus.put(loopback)
        if is_query:
            self.bus.put(DaliFrame(timestamp=time.monotonic(), status=DaliStatus.TIMEOUT, message="mock timeout"))

    def read_frame(self) -> DaliFrame | None:
        """Read the next frame from the mock bus."""
        try:
            return self.bus.get(timeout=self.READ_TIMEOUT)
        except queue.Empty:
            return None
