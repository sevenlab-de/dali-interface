# DALI Interface

A common API for different hardware realizations of a DALI interface.

## API

The interface classes implement the following API functions.

### Transmit

Transmits a DALI frame on the bus. All 8 bit frames are treated as backward frames.
When called with `block = True`, this function waits for the transmission to finish and consumes its own loopback frame.
With `block = False`, loopback frames remain in the `get`-Queue.

A frame is transmitted only after the loopback of the previous frame was read, also when that frame was transmitted with `block = False`.
The loopback is instantaneous on the DALI bus; only the communication with the interface and frames of other bus units delay it, see [Other bus units transmitting](#other-bus-units-transmitting).

```python
def transmit(self, frame: DaliFrame, block: bool = False) -> bool:
```

* `frame` (DaliFrame): frame to transmit
* `block` (bool, optional): wait for the end of transmission. Defaults to False.

* **returns** `bool` : `True` for successful transmission.
With `block = True`, `False` if the interface reported neither the loopback nor another frame on the bus within `LOOPBACK_SUPERVISION_TIMEOUT`, or if it reported an error instead of the loopback.
* **raises** `RuntimeError`: the receive thread does not run, for example after an error while reading from the interface.

#### Other bus units transmitting

If another bus unit transmits while a frame waits for the bus, the frame should rather be dropped, so the application can first react to the frame that came in.
The supported interfaces cannot do that: they keep the frame and transmit it once the bus is idle for the settling time, after any number of frames of other bus units.
Measured on the Lunatone DALI USB: while another bus unit kept the bus busy for 4 s, it waited and then transmitted its frame about 12 ms after the last frame.

As a workaround, the library waits for the loopback as long as the bus is busy:

* Frames of other bus units that the interface reports before the loopback go to the `get`-Queue, as received frames.
* With each of them the supervision of the loopback starts again.
* If the interface reports neither the loopback nor another frame within `LOOPBACK_SUPERVISION_TIMEOUT`, the interface failed.
  151 ms: the settling time of priority 5 (21.1 ms, IEC 62386-101 Table 22), a 32 bit frame with stop condition (29.9 ms), plus 100 ms for the communication with the interface.
* Anything else reported instead of the loopback, such as an interface error or a different loopback, is an error.

So a transmission can take much longer than the frame itself on a busy bus, and frames of other bus units can arrive before the loopback of a frame transmitted with `block = False`.

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
