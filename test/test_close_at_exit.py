"""
Tests for closing the interfaces left open at exit. They run without hardware.
"""

import subprocess
import sys
import textwrap

PROLOGUE = """
import logging
import sys

from dali_interface import DaliFrame, DaliMock

logging.basicConfig(level=logging.DEBUG, stream=sys.stderr, format="%(message)s")
"""


def run_python(code: str) -> subprocess.CompletedProcess[str]:
    """Run the code in a new interpreter, so its exit functions run."""
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(PROLOGUE) + textwrap.dedent(code)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_interface_left_open_is_closed_at_exit() -> None:
    """
    An interface the application does not close is closed at exit, its receive thread stops.
    """
    result = run_python(
        """
        dali = DaliMock()
        dali.transmit(DaliFrame(length=16, data=0xFF00))
        """
    )
    assert result.returncode == 0, result.stderr
    assert "close DaliMock left open at exit" in result.stderr
    assert "connection closed, thread terminated" in result.stderr


def test_interface_left_open_is_closed_after_exception() -> None:
    """
    An exception that ends the program does not leave the interface open.
    """
    result = run_python(
        """
        dali = DaliMock()
        raise RuntimeError("premature end")
        """
    )
    assert result.returncode == 1
    assert "RuntimeError: premature end" in result.stderr
    assert "close DaliMock left open at exit" in result.stderr
    assert "connection closed, thread terminated" in result.stderr


def test_closed_interface_is_not_closed_again_at_exit() -> None:
    """
    An interface the application closed is not closed again at exit.
    """
    result = run_python(
        """
        with DaliMock() as dali:
            dali.transmit(DaliFrame(length=16, data=0xFF00))
        """
    )
    assert result.returncode == 0, result.stderr
    assert "left open at exit" not in result.stderr
    assert result.stderr.count("tear down connection") == 1


def test_all_interfaces_left_open_are_closed_at_exit() -> None:
    """
    Every interface left open is closed at exit, not only the last one.
    """
    result = run_python(
        """
        first = DaliMock()
        second = DaliMock()
        closed = DaliMock()
        closed.close()
        """
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr.count("close DaliMock left open at exit") == 2
    assert result.stderr.count("connection closed, thread terminated") == 3
