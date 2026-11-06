# Hardware, data transport and command protocol

## Sensor board: existing ESP32

| Module connection | ESP32 connection |
|---|---|
| ECG signal | GPIO35 |
| Pressure signal | GPIO34 |
| IMU I2C SDA | GPIO21 |
| IMU I2C SCL | GPIO22 |
| Sensor power | Existing 3.3 V arrangement |
| Sensor ground | GND |

The current IMU address is `0x4A`. The recommended acquisition firmware is
`arduino/08_sensor_sync/08_sensor_sync.ino`; dependencies are supplied under
`vendor/libraries/`. Keep their license files when installing the libraries.

Target intervals are ECG 4 ms, pressure 50 ms, IMU 40 ms. Effective rate and
overruns must be checked from the actual timestamps. `SELECT all` interleaves
the three channels using the same ESP32 clock; each sample retains `kind`,
global `seq` and `t_ms`. USB sensor serial uses 460800 baud.

Wi-Fi uses the ESP32's local `Wearable-...` access point and HTTP endpoint
`http://192.168.4.1`. `Wearable2026` in the firmware is the existing example
hotspot password, not an account credential. This firmware is a local demo,
not a hardened network service. Battery-powered sensing still sends raw data
to a running computer, where Python performs analysis.

The original single-module sketches remain under `arduino/` for diagnostics.
The old `07_airbag_control_arduino` is a legacy power-on timer, not the active
sensor-command firmware.

## Separate air-cell board: Uno

| Uno pin | Driver input |
|---|---|
| D3 | Solenoid valve |
| D4 | Inflation pump |
| D5 | Deflation pump |
| GND | Driver signal ground |

Pump loads are connected through the existing driver board and external
power supply, not powered from controller GPIO. The shared air line feeds
five cells through the assembled splitter/tubing network. Individual cell
valves or pressure sensors are not implemented. The film-pressure sensor on
the ESP32 is not internal air-cell pressure feedback.

Use `arduino/09_airbag_command_bench/09_airbag_command_bench.ino` on the Uno,
not the ESP32. Computer-to-Uno serial is 9600 baud and newline-terminated
ASCII. Current identity is `AIRBAG_BENCH_V5`.

```text
computer -> Uno   PING / STATUS
Uno -> computer   PONG / STATUS AIRBAG_BENCH_V5 ...
computer -> Uno   ARM
Uno -> computer   OK ARM
computer -> Uno   STATUS
Uno -> computer   ... ARMED=1 PULSING=0
computer -> Uno   FIRE
Uno -> computer   OK FIRE
Uno -> computer   phase reports, then DONE FIRE
computer -> Uno   STOP (also sent during cleanup)
```

Power-on initializes outputs off. A bounded command runs 12 rounds of 12 s
inflation followed by 12 s deflation (288 s total); the Python timeout is 305 s.
STOP during inflation transitions to deflation; it is not an instantaneous
all-valves-off command. The original source and status checks are retained.
This is the existing nonhuman bench implementation, with no pressure or
breathing-phase feedback.
