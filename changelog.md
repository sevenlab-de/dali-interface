# Changelog for `dali-interface`

From v2.0.0 on, the versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html):
MAJOR.MINOR.PATCH, where a change of MAJOR breaks the API, a change of MINOR adds to it,
and a change of PATCH only fixes bugs.

## v2.0.0

- Semantic versioning, see above. The previous version was v1.15.
- `DaliFrame` has the properties `address_byte`, `instance_byte`, `opcode_byte` and `number_nibble`.

## v1.15

Breaking changes:

- `DaliInterface`, `DaliSerial` and `DaliUsb` no longer accept `max_queue_size` and `start_receive`.
  The receive thread always runs. The receive queue holds 5 frames; when it is full, the oldest frame is dropped.
- `DaliInterface.build_command_string` moved to `DaliSerial.build_command_string`.
- `DaliMock` prints the transmitted frames instead of the command strings of the serial adapter.
- `transmit` returns `bool`: `False` if `block=True` and the interface reported neither the loopback nor another
  frame on the bus within 151 ms, or an error instead of the loopback.
- Only one frame is in flight: `transmit` sends a frame after the loopback of the previous frame was read,
  also for frames transmitted with `block=False`. While other bus units transmit, the interfaces hold the frame
  back; their frames go to the receive queue and the wait for the loopback continues (see README).
- `transmit`, `query_reply` and `get` raise `RuntimeError` when the receive thread stopped after an error.
- `get` no longer returns the timeout events of the interfaces, except as the result of `query_reply`.
  The USB interface reported one after every frame. A frame with `DaliStatus.TIMEOUT` from `get` now
  only means that its timeout expired.
- `DaliUsb` reports its own frames as `DaliStatus.LOOPBACK` instead of `DaliStatus.FRAME`, like `DaliSerial`.
- `DaliUsb.last_transmit` is removed.
- `DaliFrame` objects are equal if `length` and `data` are equal; the other fields are ignored.
- `DaliFrame.timestamp` is the start of the frame. `DaliUsb` and `DaliMock` use `time.monotonic()`
  instead of `time.time()`.
- `query_reply` returns the reply as reported by the interface, which applies the reply window of IEC 62386-101.
  If the interface reports neither a reply nor a timeout within 123.3 ms, it returns `DaliStatus.INTERFACE`
  (before: a timeout after 1 s).
- Own interface implementations implement `read_frame` and `_transmit_locked` instead of `read_data`,
  `transmit` and `query_reply`.

New features and fixes:

- Blocking `transmit` waits until the frame was seen on the bus, also for send-twice frames.
- `query_reply` is thread safe: no other frame is transmitted between the request and the reply.
- `DaliMock` reports transmitted frames as loopback, and a timeout for queries.
- `DaliUsb` ignores timeout events of earlier frames.
- `query_reply` never returns a frame received before its request, like the loopback of an earlier non-blocking `transmit`.
- `query_reply` returns `DaliStatus.INTERFACE` instead of `DaliStatus.TIMEOUT` if the loopback of the request was not read,
  so `TIMEOUT` always means that no backward frame was received.
- `DaliUsb` no longer reports an identical frame of another bus unit as its own loopback.
- Frames received before a blocking `transmit` are kept in the receive queue.
- Add hardware-in-the-loop tests and the examples `blinky` and `query`.
- `DaliSerial` no longer knows the codes `0x84` to `0x87`, `0x90`, `0xA1` and `0xA4`; no firmware of the adapter reports them.
  It reports `0x88`, a corrupt frame as sent by the logger sample of the Zephyr DALI driver, as `DaliStatus.TIMING`.

## v1.14

- Summarize interface-specific error states into the generic `INTERFACE` status
  (removes `DaliStatus.GENERAL` and `DaliStatus.UNDEFINED`).
- Input lines that don't contain valid DALI frame information are ignored for
  "line"-based devices.

## v1.13

- Remove run-time typechecking. Instead the package relies on `mypy`'s static analysis.
- Fix type inconsistencies uncovered by `mypy`
- Prepare the package for publishing on PyPI
