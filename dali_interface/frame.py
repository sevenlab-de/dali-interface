"""Define the DALI frame class and its components"""

from enum import IntEnum, unique
from typing import NamedTuple


@unique
class DaliStatus(IntEnum):
    """Status for frames and events."""

    OK = 0  # interface reports OK, no error condition detected
    LOOPBACK = 1  # loopback frame - this is a frame that was sent and received back from the interface
    FRAME = 2  # normal DALI frame
    TIMEOUT = 3  # timeout occurred
    TIMING = 4  # timing error within the DALI frame detected
    INTERFACE = 5  # during operation an error occurred on the interface
    FAILURE = 6  # failure condition on the DALI bus detected
    RECOVER = 7  # DALI bus recovered (from failure)


class DaliFrame(NamedTuple):
    """DALI frame object.

    `timestamp` is the start of the frame in seconds. Each interface uses its own clock:
    the serial interface the clock of the adapter, the USB interface and the mock `time.monotonic()`
    of the host. So timestamps can only be compared between frames from the same interface.
    For events without a frame, like a timeout, it is the time the event was reported.
    Frames the library creates itself use `time.monotonic()` of the host for every interface:
    the `DaliStatus.INTERFACE` results of `transmit` and `query_reply`. The `DaliStatus.TIMEOUT`
    frame that `get` returns when its timeout expires has the timestamp 0.
    """

    timestamp: float = 0
    length: int = 0
    data: int = 0
    priority: int = 2
    send_twice: bool = False
    status: DaliStatus = DaliStatus.OK
    message: str = "OK"

    # A frame is never equal to another type. NotImplemented would fall back to the comparison of
    # plain tuples, which compares all fields, while __hash__ only hashes length and data.
    def __eq__(self, other: object, /) -> bool:
        if not isinstance(other, DaliFrame):
            return False
        return self.length == other.length and self.data == other.data

    def __ne__(self, other: object, /) -> bool:
        if not isinstance(other, DaliFrame):
            return True
        return self.length != other.length or self.data != other.data

    def __hash__(self) -> int:
        return hash((self.length, self.data))

    @property
    def address_byte(self) -> int:
        """Address byte of a forward frame: bits 15 to 8 of a 16 bit frame (IEC 62386-102),
        bits 23 to 16 of a 24 bit frame (IEC 62386-103).

        Raises:
            ValueError: the frame is neither 16 nor 24 bit long.
        """
        if self.length == 16:
            return (self.data >> 8) & 0xFF
        if self.length == 24:
            return (self.data >> 16) & 0xFF
        raise ValueError(f"a {self.length} bit frame has no address byte")

    @property
    def instance_byte(self) -> int:
        """Instance byte of a 24 bit forward frame (IEC 62386-103): bits 15 to 8.

        Raises:
            ValueError: the frame is not 24 bit long.
        """
        if self.length == 24:
            return (self.data >> 8) & 0xFF
        raise ValueError(f"a {self.length} bit frame has no instance byte")

    @property
    def opcode_byte(self) -> int:
        """Opcode byte of a 16 or 24 bit forward frame: bits 7 to 0.

        Raises:
            ValueError: the frame is neither 16 nor 24 bit long.
        """
        if self.length in (16, 24):
            return self.data & 0xFF
        raise ValueError(f"a {self.length} bit frame has no opcode byte")

    @property
    def number_nibble(self) -> int:
        """Lower 4 bits of the opcode byte, the number in commands like GO TO SCENE.

        Raises:
            ValueError: the frame is neither 16 nor 24 bit long.
        """
        return self.opcode_byte & 0x0F

    def __repr__(self) -> str:
        result = f"<{self.__class__.__module__}.{self.__class__.__name__} "
        for field in DaliFrame._fields:
            # pylint: disable=no-member
            if self.__getattribute__(field) != self._field_defaults[field]:
                # pylint: enable=no-member
                if field == "data":
                    if self.length == 8:
                        result = result + f"data=0x{self.data:02X}, "
                    elif self.length == 16:
                        result = result + f"data=0x{self.data:04X}, "
                    elif self.length == 24:
                        result = result + f"data=0x{self.data:06X}, "
                    elif self.length == 32:
                        result = result + f"data=0x{self.data:08X}, "
                    else:
                        result = result + f"data=0x{self.data:X}, "
                else:
                    result = result + f"{field}={self.__getattribute__(field)}, "
        while result[-1:] in (" ", ","):
            result = result[:-1]
        return result + ">"
