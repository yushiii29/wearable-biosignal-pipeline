# Data, provenance and evaluation

The source archive contains 53 manually selected real-device single-sensor
captures: 12 pressure, 20 IMU and 21 ECG. One ECG capture has no accepted HR
estimate, leaving 52 local feature observations. Eight published HR values
produce the poster's overall count of 60 usable observations.

The rest-context selection retains recorded seated/standing conditions,
including normal minor movements. It contains 43 captures: pressure 11,
IMU 11, ECG 21. One ECG is unestimable, leaving 42 usable rest-context records.
The ten excluded movement captures remain in the included feature table.
No raw source file was deleted or edited to obtain these subsets.

| Model | Local training inputs | Additional inputs |
|---|---|---|
| Rest pressure | 11 captures: 7 normal, 4 self-simulated | None |
| Rest IMU | 11 captures: 8 normal, 3 self-simulated | None |
| ECG source comparison | 20 normal HR estimates | 8 reported episode maxima, 7 external subjects |

Capture-level leave-one-out evaluation gives pressure 4/4 self-simulated
captures flagged and 0/7 normal false flags. IMU gives 2/3 self-simulated
captures flagged, with 1/8 normal false flags. These are exploratory results
on repeated captures, not independent-participant or clinical validation.

The ECG source comparison mixes different populations, recording devices and
summary measurements. Its fitted boundary 79.5149 BPM is not substituted for
the displayed 100 BPM project reference or a clinical criterion.

Included records use neutral IDs. Participant codes retain repeated-person
grouping without names, source timestamps, MAC addresses or free-text notes.
This does not make records independent or establish a clinical diagnosis.

Before building the feature table, all 53 original CSV and JSON pairs were
checked against their saved SHA-256 values. A private local mapping is retained
outside this repository. The shipped optimizer and signal-processing code
retain source provenance in `source_code_provenance.json`.

Raw waveforms are optional local input. `tools/import_recordings.py` copies
them into Git-ignored `data/runs/`; `tools/extract_features.py` reruns original
ECG, pressure and IMU feature extraction without editing those inputs.
The original waveform regression test becomes available after import.
