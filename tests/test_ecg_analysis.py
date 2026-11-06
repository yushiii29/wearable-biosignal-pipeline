"""算法软件检查，合成波形的已知输入不是人体准确率验证。"""
import copy
import json
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ecg_analysis import analyze_ecg,format_ecg_analysis
from lab_suite import simulated


def ecg(bpm=75, seconds=20):
    return [simulated('ecg',i/250,i,bpm=bpm) for i in range(int(seconds*250))]


class EcgAnalysisTests(unittest.TestCase):
    def test_known_synthetic_rates(self):
        for bpm in (45,60,75,120,160):
            result=analyze_ecg(ecg(bpm))
            self.assertEqual(result['status'],'estimated_full')
            self.assertAlmostEqual(result['bpm'],bpm,delta=1.5)
            json.dumps(result,allow_nan=False)

    def test_motion_segment_does_not_discard_later_clean_data(self):
        rows=ecg(75)
        for i,r in enumerate(rows):
            if 4<=r['t_ms']/1000<=13:r['ecg_adc']=4095 if i%2 else 0
        before=copy.deepcopy(rows)
        result=analyze_ecg(rows)
        self.assertEqual(rows,before)
        self.assertEqual(result['status'],'estimated_partial')
        self.assertAlmostEqual(result['bpm'],75,delta=1.5)
        self.assertGreater(result['selected_window']['start_s'],13)
        self.assertTrue(any(not w['accepted'] for w in result['windows']))
        self.assertIn('not the average heart rate of the whole recording',format_ecg_analysis(result))

    def test_inverted_signal_uses_selected_polarity(self):
        rows=ecg(90)
        for row in rows:row['ecg_adc']=4095-row['ecg_adc']
        result=analyze_ecg(rows,-1)
        self.assertAlmostEqual(result['bpm'],90,delta=1.5)

    def test_baseline_drift_preserves_pulse_detection(self):
        rows=ecg(75)
        for r in rows:r['ecg_adc']+=round(350*np.sin(r['t_ms']/1000*.8))
        result=analyze_ecg(rows)
        self.assertAlmostEqual(result['bpm'],75,delta=1.5)

    def test_flat_or_rail_signal_is_not_given_heart_rate(self):
        for value in (0,1000,4095):
            rows=ecg()
            for r in rows:r['ecg_adc']=value
            result=analyze_ecg(rows)
            self.assertIsNone(result['bpm'])
            self.assertIsNone(result['candidate_bpm'])
            self.assertEqual(result['status'],'unavailable')

    def test_continuously_clipped_signal_not_presented_as_valid_heart_rate(self):
        rows=ecg()
        for i,r in enumerate(rows):r['ecg_adc']=4095 if i%200<100 else 0
        result=analyze_ecg(rows)
        self.assertIsNone(result['bpm'])
        self.assertEqual(result['accepted_window_count'],0)
        if result['candidate_bpm'] is not None:
            self.assertIn('not a valid heart rate',format_ecg_analysis(result))

    def test_powerline_like_oscillation_is_not_a_heart_rate(self):
        rows=ecg()
        for r in rows:r['ecg_adc']=round(2000+600*np.sin(2*np.pi*50*r['t_ms']/1000))
        result=analyze_ecg(rows)
        self.assertIsNone(result['bpm'])

    def test_gaps_are_not_bridged_to_create_rr_intervals(self):
        rows=[r for r in ecg() if int(r['t_ms']/1000)%4!=3]
        result=analyze_ecg(rows)
        self.assertIsNone(result['bpm'])

    def test_too_short_slow_or_invalid_input(self):
        self.assertIsNone(analyze_ecg(ecg(seconds=3))['bpm'])
        self.assertIsNone(analyze_ecg(ecg()[::5])['bpm'])
        for value in (float('nan'),float('inf'),-1,4096):
            rows=ecg();rows[100]['ecg_adc']=value
            self.assertIsNone(analyze_ecg(rows)['bpm'])
        rows=ecg();rows[50]['t_ms']=rows[49]['t_ms']
        self.assertIsNone(analyze_ecg(rows)['bpm'])
        with self.assertRaises(ValueError):analyze_ecg(ecg(),0)


if __name__=='__main__':unittest.main()
