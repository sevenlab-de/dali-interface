import pytest

from dali_interface import DaliSerial, DaliUsb
from typing import Generator


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--serial-port", action="store", default="/dev/ttyDALI", help="Serial port for DALI-Serial-Adapter."
    )


@pytest.fixture(scope="session")
def serial_port(request: pytest.FixtureRequest) -> str:
    port_name = request.config.getoption("--serial-port")
    assert isinstance(port_name, str), "No DALI serial port specified"
    return port_name


@pytest.fixture(scope="session")
def dali_serial(serial_port: str) -> Generator[DaliSerial, None, None]:
    dali_serial = DaliSerial(serial_port)
    print(f"open dali_serial at {serial_port}")
    yield dali_serial
    dali_serial.close()


@pytest.fixture(scope="session")
def dali_usb() -> Generator[DaliUsb, None, None]:
    dali_usb = DaliUsb()
    print("open dali_usb")
    yield dali_usb
    dali_usb.close()
