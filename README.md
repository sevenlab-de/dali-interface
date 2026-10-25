# DALI Interface

A common API for different hardware realizations of a DALI interface.

## API

The interface classes implement the following API functions.

### Transmit

Transmits a DALI frame on the bus. All 8 bit frames are treated as backward frames.
When called with `block = True`, this function waits for the transmission to finish and consumes its own loopback frame.
With `block = False`, loopback frames remain in the `get`-Queue.

A frame is transmitted only after the loopback of the previous frame was read, also when that frame was transmitted with `block = False`.
The loopback is instantaneous on the DALI bus; only the communication with the interface and frames of other bus units delay it.
While other bus units transmit, the interface holds the frame back, and their frames go to the `get`-Queue.

```python
def transmit(self, frame: DaliFrame, block: bool = False) -> bool:
```

* `frame` (DaliFrame): frame to transmit
* `block` (bool, optional): wait for the end of transmission. Defaults to False.

* **returns** `bool` : `True` for successful transmission.
With `block = True`, `False` if the interface reported neither the loopback nor another frame on the bus within `LOOPBACK_SUPERVISION_TIMEOUT`, or if it reported an error instead of the loopback.
* **raises** `RuntimeError`: the receive thread does not run, for example after an error while reading from the interface.

### Get

Get the next DALI frame from the input queue.

```python
def get(self, timeout: float | None = None) -> DaliFrame:
```

* `timeout` (float | None, optional): time in seconds before the call returns.
Default is None (wait until halted).

* **returns** `DaliFrame`: time out is indicated in the frame status

All frames go through one receive queue, and `query_reply` reads its reply from that queue too.
While `query_reply` runs in another thread, `get` can take the reply, and `query_reply` then returns `DaliStatus.INTERFACE`.
So do not call `get` while a query runs in another thread.

### Query Reply

Transmit a DALI frame that is requesting a reply. Wait for either the replied data, or indicate a timeout.
Frames received before the request was seen on the bus, frames of other bus units included, are removed from the `get`-Queue, as they cannot be the reply.

```python
def query_reply(self, request: DaliFrame) -> DaliFrame:
```

* `request` (DaliFrame): DALI frame to transmit
* **returns** `DaliFrame`: the reply as reported by the interface, with one of these states:
    * `DaliStatus.FRAME`: the backward frame.
    * `DaliStatus.TIMING`: a corrupted backward frame.
      If several bus units reply at the same time, their backward frames overlap.
      According to IEC 62386-101 such a frame still counts as a backward frame, for example a YES from several control gears.
    * `DaliStatus.TIMEOUT`: no backward frame within the reply window.
    * `DaliStatus.INTERFACE`: the loopback of the request was not read (see [Transmit](#transmit)), the interface reported an error, or it reported neither a reply nor a timeout in time.

The reply window is defined by IEC 62386-101 and is not configurable:
a backward frame starts at most 12.4 ms after the end of the request, with a grey area up to 13.4 ms.
The interface applies this timing as the DALI receiver and reports either the backward frame or a timeout.
`query_reply` returns this result.
If the interface reports neither within `REPLY_SUPERVISION_TIMEOUT` (123.3 ms: reply window, backward frame and stop condition, plus 100 ms for the interface to report to the host), the interface failed and `query_reply` returns `DaliStatus.INTERFACE`.
This allowance for the interface does not extend the reply window on the bus.

### Power

Control a built in power supply. For now, this requires a Lunatone DALI USB 30 mA interface.

```python
def power(self, power: bool = False) -> None:
```

* `power` : new power setting: `True` for power on, `False` for power off

### DaliFrame

Class definition for DALI frames.
Two frames are equal if they have the same `length` and `data`; the other fields are not compared.

`timestamp` is the start of the frame in seconds.
Each interface uses its own clock: the serial interface the clock of the adapter, the USB interface and the mock `time.monotonic()` of the host.
So timestamps can only be compared between frames from the same interface.
Frames the library creates itself use `time.monotonic()` of the host for every interface: the `DaliStatus.INTERFACE` results of `transmit` and `query_reply`.
The `DaliStatus.TIMEOUT` frame that `get` returns when its timeout expires has the timestamp 0.

Properties for the parts of a forward frame:

| Property | 16 bit frame (IEC 62386-102) | 24 bit frame (IEC 62386-103) |
| --- | --- | --- |
| `address_byte` | bits 15 to 8 | bits 23 to 16 |
| `instance_byte` | – | bits 15 to 8 |
| `opcode_byte` | bits 7 to 0 | bits 7 to 0 |
| `number_nibble` | bits 3 to 0, the number in commands like GO TO SCENE | bits 3 to 0 |

For frames of other lengths, and for `instance_byte` of a 16 bit frame, they raise `ValueError`.

### DaliStatus

Class definition for status of DALI frames

## Supported Hardware

* [Lunatone 241 389 23DO](https://www.lunatone.com/wp-content/uploads/2018/03/24138923_DALI_USB_GER_D0052-1.pdf)
* Lunatone 241 389 23-30
* [BEGA 71024](https://www.bega.com/en/products/light-control/dali-usb-interface-71024/)
* [Serial based SevenLab Hardware](https://github.com/SvenHaedrich/kicad_dali_usb_lpc)

>[!NOTE]
>Using the serial interface on Windows may exhibit excessive latency.
>This can potentially be improved by tweaking the serial driver config.

## HID-USB Support

For the Lunatone USB adapter you need to copy the file `99-lunatone-dali.rules`
into the `udev` folder and reload the `udev` rules.

```shell
sudo cp 99-lunatone-dali.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
```

The provided `99-lunatone-dali.rules` file is configured by default with `MODE="0660"` (and typically `GROUP="dialout"`), so read/write access is restricted to users in the `dialout` group rather than granted to everyone.
If you explicitly want world read/write access, you can change `MODE` to `0666` in the rules file.

You can grant access to a specific user account by adding it to the `dialout` group.
Note that some Linux distributions always require a per-user permission.
To grant permission to a user named `<username>` execute:

```shell
sudo usermod -a -G dialout <username>
```

You will have to log out and then back in for the group change to take effect.

## Samples

Two samples are provided to show the basic usage for the interface.

### Blinky

`blinky` switches all control gears on the DALI bus between maximum level and off.
It sends the broadcast commands RECALL MAX LEVEL (0xFF05) and OFF (0xFF00) every 0.75 seconds.
The loop continues until it is externally interrupted.
The interface used is set by command line parameter.
Supported are `serial`, `usb`, and `mock`.
When `serial` is selected, a portname needs to be provided.

```shell
python example/blinky.py serial /dev/ttyUSB0
```

### Query

`query` sends the query QUERY CONTROL GEAR PRESENT to all control gears (broadcast, 0xFF91) and to the control gear with short address 12 (0x1991).
A control gear that receives the query answers with YES, a backward frame with the value 0xFF.
So the broadcast query is answered if there is at least one control gear on the bus.
The second query is answered only if a control gear has short address 12, otherwise it times out.
If several control gears answer at the same time, their answers overlap and arrive as a corrupted frame, which still counts as an answer.

The loop continues until it is externally interrupted.
The interface used is set by command line parameter.
Supported are `serial`, `usb`, and `mock`.
When `serial` is selected, a portname needs to be provided.

```shell
python example/query.py usb
```

## Tests

The tests in `test/test_mock.py` need no hardware.
All other tests are hardware-in-the-loop tests and need this setup:

* a Lunatone DALI USB interface,
* a SevenLab DALI serial adapter, by default at `/dev/ttyDALI`,
* both connected to the same DALI bus, with a DALI bus power supply.

No control gear or control device may be connected to the bus.
The tests send arbitrary DALI commands, including broadcast configuration commands like SET SHORT ADDRESS, that change the configuration of connected devices.

Run all tests with:

```shell
./run_hitl_local.sh
```

The script creates a virtual environment in `.venv`, installs the package with its development dependencies, and runs `pytest`.
Arguments are passed on to `pytest`, for example `--serial-port /dev/ttyUSB1` to use another serial port.
