"""Regression against the independently saved original analysis results."""
import json
from pathlib import Path
import sys
import unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from frame5_analysis import reproduce_frame5


class Frame5ReproductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.actual=reproduce_frame5()
        cls.reference=json.loads((ROOT/'models/reference_frame5.json').read_text())

    def test_coefficients_match_original_analysis(self):
        for kind in ('pressure','imu','ecg'):
            model=self.actual[kind]['model'];reference=self.reference[kind]
            np.testing.assert_allclose(model['coefficients'],reference['coefficients'],rtol=1e-10,atol=1e-10)
            self.assertAlmostEqual(model['intercept'],reference['intercept'],places=9)
        self.assertAlmostEqual(self.actual['pressure_cutoff'],self.reference['pressure_cutoff'],places=9)
        self.assertAlmostEqual(self.actual['ecg']['fitted_zero'],self.reference['ecg_fitted_cutoff'],places=9)
        for key in ('A0_g','G0_deg_per_s','acceleration_exponent','rotation_exponent','candidate_boundary'):
            self.assertAlmostEqual(self.actual['motion_score'][key],self.reference['motion_score'][key],places=9)

    def test_held_out_results_match_original_analysis(self):
        for kind in ('pressure','imu'):
            self.assertEqual(self.actual[kind]['loo_metrics'],self.reference[kind+'_loo'])
        hr=self.actual['ecg']['loo_metrics'];expected=self.reference['ecg_loo']
        self.assertEqual(hr['detected_simulated'],expected['external_flagged'])
        self.assertEqual(hr['missed_simulated'],expected['external_missed'])
        self.assertEqual(hr['flagged_normal'],expected['local_normal_flagged'])
        self.assertEqual(hr['unflagged_normal'],expected['local_normal_unflagged'])
        self.assertEqual(self.actual['counts']['all_usable_values_plus_external'],60)
        self.assertEqual(self.actual['counts']['resting_usable_feature_records'],42)


if __name__=='__main__':unittest.main()
