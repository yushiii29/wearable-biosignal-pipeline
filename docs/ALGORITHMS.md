# Algorithms and numerical parameters

## ECG

`ecg_analysis.py` preserves raw ADC values. A detection copy subtracts a
200 ms rolling median baseline and applies an approximately 12 ms moving
mean. The implementation uses odd sample widths at the measured sample rate.

Noise is estimated as `1.4826 × MAD`. The peak threshold is the maximum of
25 ADC units, five times the noise estimate, and 30% of the 99.5th percentile
of the detection signal. Local maxima closer than 300 ms are merged by
retaining the larger candidate. HR is `60 / median(RR_seconds)`.

Whole-record estimation is tried first; otherwise the latest eligible 6 s
window is reported with `scope=segment`. Checks include at least about 5 s,
adequate sample rate, timestamp continuity, clipping, amplitude, enough peaks,
and RR consistency. A segment estimate does not represent the whole capture.
Missing HR remains unknown. No default physiological value is inserted.

## Pressure

`candidate_rules.pressure_rate` first uses the median timestamp spacing to
form a uniform grid, with linear interpolation. It applies a 150 ms moving
mean with reflected padding. Threshold is `min + 0.20 × range`.

Above-threshold regions separated by less than 350 ms are merged. Regions
shorter than 100 ms are rejected. The maximum in each remaining region is
the pulse peak. With at least three peaks,
`R = 60 / median(inter_peak_seconds)`. R is detected pressure-pulse rate,
not a calibrated respiratory rate or an air-cell pressure measurement.

## IMU

For each complete capture:

```text
a_mag = sqrt(ax_g² + ay_g² + az_g²)
g_mag = sqrt(gx_dps² + gy_dps² + gz_dps²)
A = population_standard_deviation(a_mag)
G = sqrt(mean(g_mag²))
```

The existing path combines axes by magnitude; it does not add an IMU band-pass
filter. No trained activity recognizer is implemented; activity context is
provided by the operator.

## Class-balanced L2 logistic regression

`modeling.py` preserves the original NumPy Newton solver and backtracking line
search. Each training fold computes its own feature means and population
standard deviations. Classes receive weights `n / (2 × class_count)`.
L2 regularization is λ=1 on feature coefficients, not the intercept.

Pressure uses R directly. IMU uses `ln(A)` and `ln(G)`. The linear margin
is `intercept + coefficients · features`; zero is the fitted decision boundary.
The logistic mapping does not turn this small exploratory dataset into a
calibrated panic probability. ECG's external comparison uses its original
gradient tolerance 1e-7; pressure/IMU use 1e-8.

Rest-only pressure fits approximately `0.11678 × R - 3.97853`, with zero at
34.0682260969 pulses/minute. The rest-only IMU fit is equivalently expressed as:

```text
A0 = 0.008288212278579772 g
G0 = 8.203503753066949 degrees/s
S = (A/A0)^0.6497832685694458 × (G/G0)^0.773940397862071
candidate boundary S = 5.103498081984049
```

These normal baselines are an algebraic expression of the full-data fit.
Held-out validation refits raw log-feature models independently in each fold.
It does not reuse full-data baselines to fit held-out cases.

## Live runtime and command handoff

`candidate_rules.py` retains its original `candidate_capture_v1` parameters:
HR > 100, pressure R ≥ 34.7853 and context-normalized motion Q ≥ 9.15080485.
Q uses different exponents and baselines from S. The new offline profile is
not connected to the actuator branch.

Each channel needs ≥18 s of usable recording with its own minimum rate and
maximum gap checks. ECG requires confirmed rest context, and a segment-only
estimate cannot support a whole-capture trigger. Unknown values remain unknown.
Eligible crossings are combined by the existing ANY rule; the three-channel
AND result is recorded separately as an observation. Transport errors block
the command handoff.

`auto_bench_permit` additionally requires DEVICE source and explicit nonhuman
bench confirmation. The bridge checks independent controller identity, state,
arming and completion. No command is sent by offline training or demos.
