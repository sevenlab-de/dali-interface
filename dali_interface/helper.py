from .frame import DaliFrame


def build_command_string(frame: DaliFrame, is_query: bool) -> str:
    """Build a command string for a frame to send via serial connector.

    This function is shared between the DaliSerial and DaliMock classes.
    """
    if frame.length == 8:
        return f"Y{frame.data:X}\r"
    command = "Q" if is_query else "S"
    twice = "+" if frame.send_twice else " "
    return f"{command}{frame.priority} {frame.length:X}{twice}{frame.data:X}\r"
