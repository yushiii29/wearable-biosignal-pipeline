"""Exploratory capture-level markers. No diagnosis or actuator commands."""

import numpy as np

from ecg_analysis import analyze_ecg

VERSION = 'candidate_capture_v1'
PRESSURE_LIMIT = 34.7853  # detected pressure pulses per minute, not ADC or calibrated breaths
IMU_LIMIT = 9.15080485    # dimensionless
HR_LIMIT = 100.0          # resting adult reference only
BASELINES = {
    '静坐自然呼吸': (0.01237136, 7.68258450),
    '站立自然呼吸': (0.00749678, 9.82036516),
    '缓慢行走': (0.13769999, 107.29281959),
    '小跑': (0.65120219, 118.58309765),
    '小跳': (0.80531428, 113.40349031),
}
RESTING_ACTIVITIES = {'静坐自然呼吸', '站立自然呼吸'}


def pressure_rate(rows):
    """Exact 0.15 s / 20% / 0.35 s / 0.10 s method used in prior offline analysis."""
    if len(rows) < 3:
        return None, {'reason': 'Insufficient pressure samples.'}
    t = np.asarray([r['t_ms'] / 1000 for r in rows], dtype=float)
    y = np.asarray([r['pressure_adc'] for r in rows], dtype=float)
    if not np.all(np.isfinite(t)) or not np.all(np.isfinite(y)) or np.any(np.diff(t) <= 0):
        return None, {'reason': 'Invalid pressure timestamps or values.'}
    dt = float(np.median(np.diff(t)))
    if dt <= 0:
        return None, {'reason': 'Invalid pressure sampling interval.'}
    grid = np.arange(t[0], t[-1] + dt * .1, dt)
    values = np.interp(grid, t, y)
    width = max(1, int(.15 / dt) | 1)
    smooth = np.convolve(np.pad(values, width // 2, mode='reflect'),
                         np.ones(width) / width, mode='valid')
    threshold = float(smooth.min() + .2 * np.ptp(smooth))
    edges = np.diff(np.r_[False, smooth > threshold, False].astype(int))
    segments = []
    for lo, hi in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1) - 1):
        if segments and grid[lo] - grid[segments[-1][1]] < .35:
            segments[-1][1] = int(hi)
        else:
            segments.append([int(lo), int(hi)])
    peaks = [lo + int(np.argmax(smooth[lo:hi + 1])) for lo, hi in segments
             if grid[hi] - grid[lo] >= .10]
    details = {'pulse_count': len(peaks), 'threshold_adc_for_peak_finding': threshold,
               'peak_times_s': [round(float(grid[i] - grid[0]), 4) for i in peaks]}
    if len(peaks) < 3:
        return None, {**details, 'reason': 'Fewer than three usable pressure pulse peaks.'}
    return 60 / float(np.median(np.diff(grid[peaks]))), details


def imu_score(rows, activity):
    if activity not in BASELINES:
        return None, {'reason': 'Unknown activity context; an IMU normal baseline cannot be selected.'}
    if len(rows) < 2:
        return None, {'reason': 'Insufficient IMU samples.'}
    a = np.asarray([[r[k] for k in ('ax_g', 'ay_g', 'az_g')] for r in rows], dtype=float)
    g = np.asarray([[r[k] for k in ('gx_dps', 'gy_dps', 'gz_dps')] for r in rows], dtype=float)
    if not np.all(np.isfinite(a)) or not np.all(np.isfinite(g)):
        return None, {'reason': 'Invalid IMU values.'}
    A = float(np.std(np.linalg.norm(a, axis=1), ddof=0))
    G = float(np.sqrt(np.mean(np.sum(g * g, axis=1))))
    A0, G0 = BASELINES[activity]
    Q = (A / A0) ** 0.948350603 * (G / G0) ** 1.348652710
    return float(Q), {'A_g': A, 'G_dps': G, 'A0_g': A0, 'G0_dps': G0}


def _coverage(rows, minimum_hz, max_gap_s):
    if len(rows) < 2:
        return False, 'Insufficient samples.'
    t = np.asarray([r['t_ms'] / 1000 for r in rows], dtype=float)
    gaps = np.diff(t)
    if np.any(gaps <= 0):
        return False, 'Timestamps repeat or go backwards.'
    span = float(t[-1] - t[0])
    if span < 18.0:
        return False, 'The capture is shorter than approximately 20 seconds.'
    if (len(rows) - 1) / span < minimum_hz or float(gaps.max()) > max_gap_s:
        return False, 'Insufficient sampling rate or interrupted timestamps.'
    return True, ''


def analyze_synchronous(rows, activity, resting_confirmed=False, transport_ok=True, polarity=1):
    """Evaluate three channels from one capture; 'joint' is an observation, never a trigger."""
    channels = {kind: [r for r in rows if r.get('kind') == kind]
                for kind in ('pressure', 'imu', 'ecg')}
    result = {'version': VERSION, 'activity': activity, 'resting_confirmed': bool(resting_confirmed),
              'limits': {'HR_bpm_gt': HR_LIMIT, 'R_per_min_gte': PRESSURE_LIMIT,
                         'Q_gte': IMU_LIMIT}, 'channels': {}, 'joint_observation': None,
              'any_observation': None, 'trigger_channels': [],
              'actuator_command': None, 'warning': 'Candidate threshold crossings are for observation and recording only, not panic diagnosis or an air-cell trigger rule.'}
    coverage = {}
    for kind, hz, gap in (('pressure', 10, .25), ('imu', 12, .25), ('ecg', 100, .10)):
        ok, reason = _coverage(channels[kind], hz, gap)
        coverage[kind] = ok
        result['channels'][kind] = {'sample_count': len(channels[kind]), 'value': None,
                                    'crossed': None, 'reason': reason if not ok else ''}
    if coverage['pressure']:
        value, details = pressure_rate(channels['pressure'])
        result['channels']['pressure'].update(value=value, crossed=value >= PRESSURE_LIMIT if value is not None else None,
                                               reason=details.get('reason', ''), details=details)
    if coverage['imu']:
        value, details = imu_score(channels['imu'], activity)
        result['channels']['imu'].update(value=value, crossed=value >= IMU_LIMIT if value is not None else None,
                                          reason=details.get('reason', ''), details=details)
    if coverage['ecg']:
        analysis = analyze_ecg(channels['ecg'], polarity)
        value = analysis['bpm']
        valid_context = activity in RESTING_ACTIVITIES and resting_confirmed
        reason = '' if valid_context else 'HR>100 can be interpreted only for an adult at rest; this context is not confirmed.'
        if value is None:
            reason = 'Heart rate unknown: ' + analysis['explanation']
        result['channels']['ecg'].update(value=value,
            crossed=value > HR_LIMIT if value is not None and valid_context else None,
            reason=reason, analysis=analysis)
    aligned = False
    if all(coverage.values()):
        starts = [channels[k][0]['t_ms'] for k in channels]
        ends = [channels[k][-1]['t_ms'] for k in channels]
        aligned = max(starts) - min(starts) <= 1000 and max(ends) - min(ends) <= 1000
    result['aligned_capture'] = aligned
    # Partial ECG estimates belong to a shorter sub-interval and cannot support a whole-capture AND.
    whole_ecg = result['channels']['ecg'].get('analysis', {}).get('scope') == 'full'
    values = [result['channels'][k]['crossed'] for k in ('pressure', 'imu', 'ecg')]
    eligible = {k: result['channels'][k]['crossed'] for k in ('pressure', 'imu', 'ecg')}
    if not whole_ecg:
        eligible['ecg'] = None
    if transport_ok:
        result['trigger_channels'] = [k for k, crossed in eligible.items() if crossed is True]
        if result['trigger_channels']:
            result['any_observation'] = True
        elif all(crossed is False for crossed in eligible.values()):
            result['any_observation'] = False
    if aligned and transport_ok and whole_ecg and all(v is not None for v in values):
        result['joint_observation'] = all(values)
    else:
        result['joint_reason'] = ('Channels are not aligned, transmission problems occurred, ECG can be estimated only for a segment, or a channel/activity context is unknown. No same-recording three-threshold assessment is made.')
    return result


