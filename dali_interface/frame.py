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
    """DALI frame object."""

    timestamp: float = 0
    length: int = 0
    data: int = 0
    priority: int = 2
    send_twice: bool = False
    status: DaliStatus = DaliStatus.OK
    message: str = "OK"

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
