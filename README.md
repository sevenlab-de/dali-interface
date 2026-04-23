# DALI Interface

A common API for different hardware realizations of a DALI interface.

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

The provided `99-lunatone-dali.rules` file is configured by default with `MODE="0660"`
(and typically `GROUP="dialout"`), so read/write access is restricted to users in
the `dialout` group rather than granted to everyone. If you explicitly want world
read/write access, you can change `MODE` to `0666` in the rules file.

You can grant access to a specific user account by adding it to the `dialout` group.
Note that some Linux distributions always require a per-user permission. To grant
permission to a user named `<username>` execute:

```shell
sudo usermod -a -G dialout <username>
```

You will have to log out and then back in for the group change to take effect.

## Samples

One sample is provided to show the basic usage for the interface.

### Blinky

`blinky` makes all control gears connected to the interface's DALI bus change between off and maximum intensity.
The loop continues until it is externally interrupted.
The interface used is set by command line parameter.
Supported are `serial`, `usb`, and `mock`.
When `serial` is selected, a portname needs to be provided.

```shell
python blinky.py serial /dev/ttyUSB0
```

## API

The interface classes implement the following API functions.

### Transmit

Transmits a DALI frame on the bus. All 8 bit frames are treated as backward frames.

```python
    def transmit(self, frame: DaliFrame, block: bool = False) -> None:
```

* `frame` (DaliFrame): frame to transmit
* `block` (bool, optional): wait for the end of transmission. Defaults to False.

### Get

Get the next DALI frame from the input queue.

```python
    def get(self, timeout: float | None = None) -> DaliFrame:
```

* `timeout` (float | None, optional): time in seconds before the call returns.
Default is None (wait until halted).

* **returns** `DaliFrame`: time out is indicated in the frame status

### Query Reply

Transmit a DALI frame that is requesting a reply. Wait for either
the replied data, or indicate a timeout.

```python
    def query_reply(self, request: DaliFrame) -> DaliFrame:
```

* `request` (DaliFrame): DALI frame to transmit
* **returns** `DaliFrame`: the received reply.
If no reply was received a frame with `DaliStatus:TIMEOUT` is returned

### Power

Control a built in power supply. For now, this requires a Lunatone DALI USB 30 mA
interface.

```python
    def power(self, power: bool = False) -> None:
```

* `power` : new power setting: `True` for power on, `False` for power off

### DaliFrame

Class definition for DALI frames

### DaliStatus

Class definition for status of DALI frames
