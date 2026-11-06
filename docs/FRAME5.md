# Frame 5 implementation map

The poster summarizes both offline analysis and a live prototype. This table
identifies their separate source files and validation scopes.

| Stage | Inputs and outputs | Source |
|---|---|---|
| A — Sample | ECG ADC, pressure ADC, accelerometer/gyro; device time and sequence | `arduino/08_sensor_sync/08_sensor_sync.ino` |
| A — Transport | Wi-Fi HTTP or USB serial, validated packets | `wifi_transport.py`, `lab_suite.py`, `combined_panel.py` |
| A — Save | One raw CSV and one metadata JSON per capture | `lab_suite.save_capture` |
| B — ECG | Raw samples → detection signal → candidate R peaks → HR estimate | `ecg_analysis._peaks`, `_window`, `analyze_ecg` |
| B — Pressure | Timestamps/ADC → interpolation and smoothing → pulses → pulse rate | `candidate_rules.pressure_rate` |
| B — Motion | Three-axis acceleration and gyro → magnitude → A/G features | `candidate_rules.imu_score`, `tools/extract_features.py` |
| C — Fit | One feature row per capture → standardized weighted L2 logistic regression | `modeling.fit_ridge_logistic` |
| C — Test | Hold one complete capture out and refit all training transforms | `frame5_analysis.fit_capture_model` |
| C — Export | Rest-only coefficients, cutoffs, folds and source-confounded ECG comparison | `tools/reproduce_frame5.py`, `models/` |
| D — Quality and rule | Approximately 20 s; usable coverage, transport and context → candidate crossing | `candidate_rules.analyze_synchronous` |
| D — Computer handoff | Identify Uno → STATUS → ARM → FIRE → completion → STOP | `airbag_bridge.py` |
| D — Actuation | Digital pump/valve phases, 12 s inflate / 12 s deflate / 12 cycles | `arduino/09_airbag_command_bench/09_airbag_command_bench.ino` |

## Versions shown together on the poster

| Item | Frame 5 offline rest-only analysis | Existing live candidate runtime |
|---|---|---|
| Pressure | R cutoff 34.0682260969 | R cutoff 34.7853 |
| IMU | S_rest_v1 cutoff 5.1034980820 | Q cutoff 9.15080485 |
| IMU normalization | One normal rest baseline, 8 captures | Context-specific normal baselines |
| IMU exponents | 0.6497832686 and 0.7739403979 | 0.948350603 and 1.348652710 |
| Heart rate | Fitted comparison zero 79.5149; displayed project reference 100 | Strict HR > 100 only when resting context is confirmed |
| Output | Offline model/validation JSON | Optional separate nonhuman bench path |

The poster uses a rounded H ≥ 100 label. The preserved runtime comparator is
**H > 100**; equality does not cross the active HR rule. This packaging step
does not change that behavior.

## Current physical scope

Three-channel nonhuman acquisition has been tested in the existing project.
The offline training set contains separate sensor captures, not paired
three-channel panic events. Real physiological validation of a fused trigger
has not been performed. The current V5 Uno has been exercised for single
inflate/deflate rounds; its complete 12-round physical sequence is unverified.
It has no pressure, volume or breathing-phase feedback.
