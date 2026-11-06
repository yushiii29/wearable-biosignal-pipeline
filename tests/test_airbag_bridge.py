"""Bench protocol checks. No physical controller or pump is used."""
import sys
import unittest
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from airbag_bridge import (auto_bench_permit, check_bench_controller,
                           current_candidate_status, send_bench_pulse)


class FakeUno:
    def __init__(self, status='STATUS AIRBAG_BENCH_V5 OUTPUTS=0 ARMED=0 PULSING=0'):
        self.status = status
        self.responses = deque([b'READY AIRBAG_BENCH_V5\n'])
        self.writes = []
        self.closed = False

    def readline(self):
        return self.responses.popleft() if self.responses else b''

    def write(self, raw):
        self.writes.append(raw)
        if raw == b'STATUS\n':
            self.responses.append((self.status+'\n').encode())
        elif raw == b'ARM\n':
            self.status = self.status.replace('ARMED=0', 'ARMED=1')
            self.responses.append(b'OK ARM\n')
        elif raw == b'FIRE\n':
            self.responses.extend([b'OK FIRE\n',b'PHASE DEFLATE\n',b'DONE FIRE\n'])
        elif raw == b'PING\n':
            self.responses.append(b'PONG AIRBAG_BENCH_V5\n')

    def close(self):
        self.closed = True


class AirbagBridgeTests(unittest.TestCase):
    def test_auto_accepts_one_valid_crossing_and_real_source(self):
        analysis = {'version':'candidate_capture_v1','any_observation':True,
                    'joint_observation':False,
                    'channels':{'pressure':{'crossed':True},'imu':{'crossed':False},
                                'ecg':{'crossed':None}}}
        status = current_candidate_status(analysis)
        self.assertFalse(status['wearable_actuation_permitted'])
        self.assertTrue(status['bench_auto_candidate'])
        self.assertEqual(auto_bench_permit(analysis,'DEVICE',True).any_channel_crossed, True)
        for changed in ({'any_observation':False},{'any_observation':None},
                        {'channels':{'pressure':{'crossed':False},'imu':{'crossed':False},
                                     'ecg':{'crossed':None}}}):
            with self.assertRaises(ValueError):
                auto_bench_permit({**analysis,**changed},'DEVICE',True)
        with self.assertRaises(ValueError):
            auto_bench_permit(analysis,'SIMULATED',True)
        with self.assertRaises(ValueError):
            auto_bench_permit(analysis,'DEVICE',False)

    def sample_permit(self):
        analysis = {'version':'candidate_capture_v1','any_observation':True,
                    'channels':{'pressure':{'crossed':False},'imu':{'crossed':True},
                                'ecg':{'crossed':None}}}
        return auto_bench_permit(analysis,'DEVICE',True)

    def test_read_only_probe_and_disabled_output(self):
        uno = FakeUno()
        factory = lambda *args, **kwargs: uno
        self.assertIn('OUTPUTS=0',check_bench_controller('/dev/fake-uno',factory))
        self.assertEqual(uno.writes,[b'STATUS\n'])
        permit = self.sample_permit()
        uno = FakeUno('STATUS AIRBAG_BENCH_V5 OUTPUTS=0 ARMED=0 PULSING=0')
        with self.assertRaisesRegex(RuntimeError,'not enabled'):
            send_bench_pulse('/dev/fake-uno',permit,serial_factory=lambda *args,**kwargs:uno)
        self.assertNotIn(b'FIRE\n',uno.writes)
        self.assertTrue(uno.closed)

    def test_bench_command_requires_distinct_port_and_arms_one_cycle(self):
        permit = self.sample_permit()
        with self.assertRaisesRegex(ValueError,'different serial port'):
            send_bench_pulse('/dev/same',permit,sensor_port='/dev/same')
        uno = FakeUno('STATUS AIRBAG_BENCH_V5 OUTPUTS=1 ARMED=0 PULSING=0')
        result = send_bench_pulse('/dev/fake-uno',permit,serial_factory=lambda *args,**kwargs:uno)
        self.assertEqual(result['completed'],'DONE FIRE')
        self.assertEqual(uno.writes,[b'STATUS\n',b'ARM\n',b'STATUS\n',b'FIRE\n',b'STOP\n'])
        self.assertTrue(uno.closed)


if __name__ == '__main__':
    unittest.main()
