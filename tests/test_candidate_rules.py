"""Regression checks against the saved offline features and conservative joint gating."""
import csv
import hashlib
import json
import math
import sys
import unittest
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEMO))
from candidate_rules import analyze_synchronous, imu_score, pressure_rate
from lab_suite import simulated


class CandidateRulesTests(unittest.TestCase):
    def test_any_valid_channel_can_cross_without_other_channel_results(self):
        rows = [simulated('imu', i * .04, i, control=50) for i in range(501)]
        result = analyze_synchronous(rows, '静坐自然呼吸')
        self.assertTrue(result['channels']['imu']['crossed'])
        self.assertIsNone(result['channels']['pressure']['crossed'])
        self.assertIsNone(result['channels']['ecg']['crossed'])
        self.assertTrue(result['any_observation'])
        self.assertEqual(result['trigger_channels'], ['imu'])
        self.assertIsNone(result['joint_observation'])
        self.assertIsNone(analyze_synchronous(rows, '静坐自然呼吸', transport_ok=False)['any_observation'])

    @unittest.skipUnless((DEMO/'data/runs/可用于比较').exists(), 'Optional private waveform dataset is not imported')
    def test_saved_pressure_and_imu_match_offline_features(self):
        features = json.loads((DEMO/'analysis/20261101_threshold_review/features.json').read_text())
        by_id = {r['csv_sha256']: r for r in features}
        checked = {'pressure':0, 'imu':0}
        for kind in checked:
            for path in (DEMO/'data/runs/可用于比较').glob(f'*_{kind}_DEVICE_*.csv'):
                meta = json.loads(path.with_suffix('.json').read_text())
                reference = by_id.get(hashlib.sha256(path.read_bytes()).hexdigest())
                if reference is None:
                    continue
                wanted = {'t_ms','pressure_adc','ax_g','ay_g','az_g','gx_dps','gy_dps','gz_dps'}
                with path.open(encoding='utf-8-sig') as source:
                    rows = [{k:float(v) for k,v in row.items() if k in wanted and v}
                            for row in csv.DictReader(source)]
                if kind == 'pressure':
                    actual,_ = pressure_rate(rows)
                    expected = reference['pressure_pulse_rate_ibi_per_min']
                else:
                    actual, details = imu_score(rows,meta['condition'])
                    if actual is None:
                        continue
                    expected = ((reference['accel_norm_sd_g']/details['A0_g'])**.948350603 *
                                (reference['gyro_rms_dps']/details['G0_dps'])**1.348652710)
                if actual is not None and expected is not None:
                    self.assertAlmostEqual(actual, expected, places=8)
                    checked[kind] += 1
        self.assertGreaterEqual(checked['pressure'], 12)
        self.assertGreaterEqual(checked['imu'], 17)

    def test_joint_requires_same_complete_capture_and_rest_context(self):
        rows = []
        seq = 0
        for ms in range(0,20001,4):
            t = ms/1000
            ecg = simulated('ecg',t,seq,bpm=75)
            ecg['t_ms'] = ms
            rows.append(ecg)
            seq += 1
            if ms%40 == 0:
                imu = simulated('imu',t,seq,control=20)
                imu['t_ms'] = ms
                rows.append(imu)
                seq += 1
            if ms%100 == 0:
                for offset in (0,50):
                    at = ms+offset
                    if at>20000:
                        continue
                    p = simulated('pressure',at/1000,seq)
                    p['t_ms'] = at
                    p['pressure_adc'] = round(1400+700*max(0,math.sin(2*math.pi*at/2000))**6)
                    rows.append(p)
                    seq += 1
        result = analyze_synchronous(rows,'静坐自然呼吸',True)
        self.assertEqual(result['joint_observation'],False)
        self.assertIsNone(result['actuator_command'])
        self.assertIsNone(analyze_synchronous(rows,'静坐自然呼吸',False)['joint_observation'])
        self.assertIs(analyze_synchronous(rows,'站立自然呼吸',True)['channels']['ecg']['crossed'],False)
        self.assertIsNone(analyze_synchronous(rows,'缓慢行走',True)['channels']['ecg']['crossed'])
        self.assertIsNone(analyze_synchronous(rows,'未知动作',True)['joint_observation'])
        self.assertIsNone(analyze_synchronous(rows,'静坐自然呼吸',True,False)['joint_observation'])
        self.assertIsNone(analyze_synchronous(rows[:1000],'静坐自然呼吸',True)['joint_observation'])


if __name__ == '__main__':
    unittest.main()
