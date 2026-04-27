"""Define the DALI frame class and its components"""

from enum import IntEnum, unique
from typing import NamedTuple


@unique
class DaliStatus(IntEnum):
    """Status for frames and events."""

    OK = 0
    LOOPBACK = 1
    FRAME = 2
    TIMEOUT = 3
    TIMING = 4
    INTERFACE = 5
    FAILURE = 6
    RECOVER = 7
    GENERAL = 8
    UNDEFINED = 9


class DaliFrame(NamedTuple):
    """DALI frame object."""

    timestamp: float = 0
    length: int = 0
    data: int = 0
    priority: int = 2
    send_twice: bool = False
    status: DaliStatus = DaliStatus.OK
    message: str = "OK"

    def __eq__(self, __value: object) -> bool:
        if not isinstance(__value, DaliFrame):
            return NotImplemented
        return self.length == __value.length and self.data == __value.data

    def __ne__(self, __value: object) -> bool:
        if not isinstance(__value, DaliFrame):
            return NotImplemented
        return self.length != __value.length or self.data != __value.data

    def __hash__(self) -> int:
        return hash((self.length, self.data))

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
