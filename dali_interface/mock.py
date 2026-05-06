"""Mock DALI interface for testing."""

import logging
import time

from .dali_interface import DaliInterface
from .frame import DaliFrame, DaliStatus
from . import helper

logger = logging.getLogger(__name__)


class DaliMock(DaliInterface):
    """Mock class for DALI interface."""

    def _transmit_locked(self, frame: DaliFrame, is_query: bool = False) -> None:
        """Mock transmission of DALI frame."""
        print(helper.build_command_string(frame, is_query))
        return

    def query_reply(self, request: DaliFrame) -> DaliFrame:
        """Mock DALI frame query."""
        print(helper.build_command_string(request, True))
        return DaliFrame(
            timestamp=time.time(),
            length=0,
            data=0,
            status=DaliStatus.TIMEOUT,
            message="mock timeout",
        )

    def read_frame(self) -> None:
        """Stub implementation."""
        raise NotImplementedError("Mock class has no read implementation")
