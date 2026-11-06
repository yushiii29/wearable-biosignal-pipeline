# Data included in this repository

`features/recordings.json` contains 53 capture-level feature records with neutral
capture identifiers, no raw waveforms, participant names, timestamps, device
identities or free-text notes. Labels describe normal tasks and self-simulated
actions. These are repeated captures, not 53 independent participants.

`external/published_hr.json` contains eight transcribed numerical observations
with their original paper citation. They are episode maximum heart rates, not
project measurements. The original paper PDF is linked, not redistributed.

The feature tables reproduce the offline model fits without access to private
waveforms. Raw-feature extraction and historical waveform replay require the
original paired CSV/JSON files in `data/runs/`, which is ignored by Git.
Use `python tools/import_recordings.py /path/to/saved/runs` to import a local copy.
