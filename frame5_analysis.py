"""Portable reproduction of the offline models shown in portfolio Frame 5.

No code in this module connects to hardware or sends actuator commands.
"""
import json
from pathlib import Path
import numpy as np
from modeling import fit_ridge_logistic, metrics

ROOT = Path(__file__).resolve().parent


def load_features():
    return json.loads((ROOT/'data/features/recordings.json').read_text())['records']


def fit_capture_model(rows, keys, log=False, tolerance=1e-8):
    rows = [r for r in rows if all(r['features'].get(k) is not None for k in keys)]
    X = np.asarray([[r['features'][k] for k in keys] for r in rows], float)
    if log:
        if np.any(X <= 0):
            raise ValueError('Log features must be positive.')
        X = np.log(X)
    y = np.asarray([r['group'] != 'normal' for r in rows], int)
    model = fit_ridge_logistic(X, y, gradient_tolerance=tolerance)
    score = model['intercept'] + X @ model['coefficients']
    held_out = []
    for i, row in enumerate(rows):
        mask = np.arange(len(y)) != i
        # Means, scales, class weights and coefficients are fitted in each fold.
        fold = fit_ridge_logistic(X[mask], y[mask], gradient_tolerance=tolerance)
        margin = float(fold['intercept'] + X[i] @ fold['coefficients'])
        held_out.append({'capture_id': row['id'], 'group': row['group'],
                         'margin': margin, 'predicted_group': 'simulated_like' if margin >= 0 else 'normal_like'})
    return {'model': model, 'feature_names': keys, 'transform': 'log' if log else 'raw',
            'capture_ids': [r['id'] for r in rows],
            'training_metrics': metrics(y, score),
            'loo_metrics': metrics(y, [r['margin'] for r in held_out]),
            'loo_predictions': held_out}


def reproduce_frame5():
    records = load_features()
    rest = [r for r in records if r['resting_context']]
    pressure = fit_capture_model([r for r in rest if r['kind']=='pressure'], ['pressure_rate'])
    imu = fit_capture_model([r for r in rest if r['kind']=='imu'], ['accel_sd','gyro_rms'], log=True)
    normal_imu = [r for r in rest if r['kind']=='imu' and r['group']=='normal']
    baseline = np.median([[r['features']['accel_sd'],r['features']['gyro_rms']] for r in normal_imu], axis=0)
    beta = np.asarray(imu['model']['coefficients'])
    relative_intercept = imu['model']['intercept'] + float(beta @ np.log(baseline))
    motion_score = {'name':'S_rest_v1', 'A0_g':float(baseline[0]), 'G0_deg_per_s':float(baseline[1]),
                    'acceleration_exponent':float(beta[0]), 'rotation_exponent':float(beta[1]),
                    'candidate_boundary':float(np.exp(-relative_intercept))}
    pressure_cutoff = -pressure['model']['intercept']/pressure['model']['coefficients'][0]
    external = json.loads((ROOT/'data/external/published_hr.json').read_text())['observations']
    local_ecg = [r for r in records if r['kind']=='ecg' and r['features']['heart_rate'] is not None]
    hr_rows = [{**r, 'features':{'HR':r['features']['heart_rate']}} for r in local_ecg]
    hr_rows += [{'id':f"external_subject_{r['subject']}_episode_{r['episode']}",
                 'group':'external_episode_maximum', 'features':{'HR':r['hr_max_bpm']}}
                for r in external]
    ecg = fit_capture_model(hr_rows, ['HR'], tolerance=1e-7)
    ecg['model']['label_semantics'] = '0: local normal HR estimate; 1: published episode maximum; source-confounded'
    ecg['fitted_zero'] = -ecg['model']['intercept']/ecg['model']['coefficients'][0]
    ecg['display_watch_range_bpm'] = [ecg['fitted_zero'], 100.0]
    ecg['display_project_cutoff_bpm'] = 100.0
    valid_local = sum(any(v is not None for v in r['features'].values()) for r in records)
    return {'profile':'frame5_offline_rest_v1',
            'counts':{'local_captures':len(records), 'local_captures_with_feature':valid_local,
                      'resting_captures':len(rest), 'resting_usable_feature_records':sum(any(v is not None for v in r['features'].values()) for r in rest),
                      'external_hr_values':len(external), 'all_usable_values_plus_external':valid_local+len(external),
                      'local_ecg_with_hr':len(local_ecg), 'rest_pressure':len(pressure['capture_ids']),
                      'rest_imu':len(imu['capture_ids'])},
            'pressure':pressure, 'imu':imu, 'ecg':ecg,
            'pressure_cutoff':float(pressure_cutoff), 'motion_score':motion_score,
            'limitations':[
                'Normal vs self-simulated tasks; no validated panic classifier.',
                'Published HR maxima and local HR estimates have different sources and summary definitions.',
                'Leave-one-capture-out is exploratory; repeated captures are not independent participants.',
                'These offline parameters are not substituted into candidate_rules.py.',
                'No actuator command is sent by this reproduction.',
            ]}


def motion_score(A, G, parameters):
    """The exact rest-only score; never mix this with the legacy Q cutoff."""
    if not np.isfinite([A,G]).all() or A < 0 or G < 0:
        raise ValueError('Finite nonnegative motion features are required.')
    return float((A/parameters['A0_g'])**parameters['acceleration_exponent'] *
                 (G/parameters['G0_deg_per_s'])**parameters['rotation_exponent'])
