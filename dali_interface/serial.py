"""Specific DALI interface implementation for SevenLab serial device."""

import logging
from typing import Final, Tuple

import serial

from .dali_interface import DaliInterface
from .frame import DaliFrame, DaliStatus
from . import helper

logger = logging.getLogger(__name__)


class DaliSerial(DaliInterface):
    """Class for serial communication DALI interface."""

    DEFAULT_BAUDRATE: Final[int] = 500000
    # see: https://github.com/SvenHaedrich/dali_usb_lpc1114/blob/main/doc/messages.md
    _MAX_BIT_LENGTH: Final[int] = 32
    _TIMEOUT: Final[int] = 0x81
    _BAD_START_BIT_TIMING: Final[int] = 0x82
    _BAD_DATA_BIT_TIMING: Final[int] = 0x83
    _COLLISION_LOOPBACK: Final[int] = 0x84
    _COLLISION_NO_CHANGE: Final[int] = 0x85
    _COLLISION_WRONG_STATE: Final[int] = 0x86
    _SETTLING_TIME: Final[int] = 0x87
    _SYSTEM_IDLE: Final[int] = 0x90
    _SYSTEM_FAILURE: Final[int] = 0x91
    _SYSTEM_RECOVERED: Final[int] = 0x92
    _COMMAND_NOT_PROCESSED: Final[int] = 0xA0
    _COMMAND_BAD_ARGUMENT: Final[int] = 0xA1
    _QUEUE_IS_FULL: Final[int] = 0xA2
    _COMMAND_BAD: Final[int] = 0xA3
    _BUFFER_OVERFLOW: Final[int] = 0xA4

    def __init__(
        self,
        portname: str,
        baudrate: int = DEFAULT_BAUDRATE,
        transparent: bool = False,
    ) -> None:
        """open serial port for DALI communication

        Args:
            portname (str): path to serial port
            baudrate (int, optional): baudrate. Defaults to DEFAULT_BAUDRATE.
            transparent (bool, optional): print echo to console. Defaults to False.
        """
        logger.debug("open serial port")
        self.port = serial.Serial(  # pylint: disable=no-member
            port=portname, baudrate=baudrate, timeout=0.2
        )
        try:
            # This only works on Posix systems.
            self.port.set_low_latency_mode(True)
        except Exception:
            # This can fail with various exceptions depending on operating system
            # and interface configuration. So, we catch them all.
            # Not having low latency mode may result in degraded performance.
            # That is still sufficient for some use-cases though and it's
            # better than no support at all.
            logger.warning("Failed to set low latency mode. Continue anyway.")
            pass
        super().__init__()
        self.transparent = transparent
        # components for reply timeout
        # 10.5 ms inter frame timing according to iec 62386-101
        # 2 ms possible delay for usb time slices - going back and forth
        # frame duration (9=start bit + 8 data bits)
        self.reply_timeout = (10.5 + 2) / 1000 + 9 / self.DALI_BAUD

    @staticmethod
    def _get_status_and_last_error(  # pylint: disable=too-many-return-statements
        length: int, data: int, loopback: bool
    ) -> Tuple[DaliStatus, str]:
        """Interpret received information."""
        if 0 <= length <= DaliSerial._MAX_BIT_LENGTH:
            if loopback:
                return DaliStatus.LOOPBACK, "LOOPBACK FRAME"
            return DaliStatus.FRAME, "NORMAL FRAME"
        if length < DaliSerial._TIMEOUT:
            return DaliStatus.OK, "OK"
        if length == DaliSerial._TIMEOUT:
            return DaliStatus.TIMEOUT, "TIMEOUT"
        if length == DaliSerial._BAD_START_BIT_TIMING:
            bit = data & 0x0FF
            timer_us = (data >> 8) & 0x0FFFFF
            return (
                DaliStatus.TIMING,
                f"ERROR TIMING: START - BIT: {bit} - TIME: {timer_us} USEC",
            )
        if length == DaliSerial._BAD_DATA_BIT_TIMING:
            bit = data & 0x0FF
            timer_us = (data >> 8) & 0x0FFFFF
            return (
                DaliStatus.TIMING,
                f"ERROR TIMING: DATA - BIT: {bit} - TIME: {timer_us} USEC",
            )
        if length in (
            DaliSerial._COLLISION_LOOPBACK,
            DaliSerial._COLLISION_NO_CHANGE,
            DaliSerial._COLLISION_WRONG_STATE,
        ):
            return DaliStatus.TIMING, "ERROR: COLLISION DETECTED"
        if length == DaliSerial._SYSTEM_FAILURE:
            return DaliStatus.FAILURE, "ERROR: SYSTEM FAILURE"
        if length == DaliSerial._SYSTEM_RECOVERED:
            return DaliStatus.RECOVER, "SYSTEM RECOVER"
        if length in (
            DaliSerial._COMMAND_NOT_PROCESSED,
            DaliSerial._COMMAND_BAD_ARGUMENT,
            DaliSerial._QUEUE_IS_FULL,
            DaliSerial._COMMAND_BAD,
        ):
            return DaliStatus.INTERFACE, "ERROR: INTERFACE"
        return DaliStatus.UNDEFINED, f"ERROR: CODE 0x{length:02X}"

    @staticmethod
    def parse(line: str) -> DaliFrame:
        """parse a string into a DALI frame

        Args:
            line (str): input string, curly braces around DALI information required

        Returns:
            DaliFrame: DALI frame
        """
        timestamp: float = 0
        length: int = 0
        data: int = 0
        try:
            start = line.find("{") + 1
            end = line.find("}")
            payload = line[start:end]
            timestamp = int(payload[0:8], 16) / 1000.0
            loopback = payload[8] == ">"
            length = int(payload[9:11], 16)
            data = int(payload[12:20], 16)
            status, message = DaliSerial._get_status_and_last_error(length, data, loopback)
            return DaliFrame(
                timestamp=timestamp,
                length=length,
                data=data,
                status=status,
                message=message,
            )
        except ValueError:
            return DaliFrame(
                timestamp=timestamp,
                length=length,
                data=data,
                status=DaliStatus.GENERAL,
                message="value error",
            )

    def read_frame(self) -> DaliFrame | None:
        """Read a line from the serial port."""
        line = self.port.readline().decode(encoding="ascii", errors="ignore").strip()
        if self.transparent:
            print(line, end="")
        if len(line) > 0:
            logger.debug(f"received line <{line}> from serial")
            return self.parse(line)
        return None

    def _transmit_locked(self, frame: DaliFrame, is_query: bool = False) -> None:
        """Transmit a DALI frame via serial connector."""
        command_string = helper.build_command_string(frame, is_query)
        self.port.write(command_string.encode(encoding="ascii"))

    def close(self) -> None:
        """
        Close the serial port after closing the base class.
        """
        super().close()
        self.port.close()
