# Sources and dependencies

## Project source

The Python capture modules, filtering/feature functions, candidate rules,
serial bridge, notebooks and firmware were collected from the existing
`sensor_demos` project. Original module hashes are recorded in
`source_code_provenance.json`. Packaging was performed on 2026-11-06.

The portable model reproduction preserves the original class-balanced,
L2-regularized NumPy optimizer. Its numerical tolerance is an explicit
argument so pressure/IMU and the external HR comparison retain their original
settings. Offline parameters and live candidate parameters are documented
separately; the working project's actuator path was not replaced.

## External HR observations

Taylor et al., *Ambulatory heart rate changes during panic attacks*,
Table 1, p.264. DOI: [10.1016/0022-3956(82)90004-8](https://doi.org/10.1016/0022-3956(82)90004-8).
[Source paper](https://labs.la.utexas.edu/telch/files/2015/02/Ambulatory-Heart-Rate.pdf).

Eight numerical episode maxima are transcribed with subject/episode and
measurement semantics in `data/external/published_hr.json`. The paper PDF
and scans are not distributed in this repository.

## Hardware libraries

`vendor/libraries/DFRobot_Multi_DOF_IMU` and
`vendor/libraries/DFRobot_RTU-master` retain their upstream source and license
files. Hardware module references:

- [DFRobot SEN0213 ECG](https://wiki.dfrobot.com/sen0213/)
- [DFRobot SEN0616 pressure](https://wiki.dfrobot.com/sen0616/)
- [DFRobot SEN0696 IMU](https://wiki.dfrobot.com/sen0696/)

Runtime dependencies are NumPy, Matplotlib, PySerial, ipywidgets and JupyterLab.
The existing macOS dependency snapshot is supplied for provenance; a new
installation uses `requirements.txt`.
