"""本地虚拟 HTTP 设备测试；不代表 ESP32 射频、真实采样率或人体心电验证。"""
import asyncio
import csv
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('MPLBACKEND', 'Agg')
from lab_suite import DEVICE_OWNERS, SensorPanel, parse_packet, simulated
from combined_panel import CombinedPanel
from wifi_transport import PROTOCOL, WifiDevice, normalize_address


class VirtualDevice:
    def __init__(self):
        self.kind = 'esp32'
        self.token = None
        self.running = False
        self.started = None
        self.end_seq = 0
        self.stream = 0
        self.boot = 'test-boot'
        self.skip = 0
        self.poll_failure = False
        self.wrong_kind = False
        self.firmware = 'sensor_wifi_v1'

    def state(self):
        count = int((time.monotonic()-self.started)*250) if self.running else self.end_seq
        return dict(protocol=PROTOCOL, firmware=self.firmware, device_id='virtual-device',
                    boot_id=self.boot, stream_id=self.stream, kind=self.kind,
                    oldest_seq=self.skip, next_seq=max(count, self.skip), running=self.running,
                    sampling_overruns=0, error='', ssid='Wearable-test')

    def __enter__(self):
        device = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, code, payload):
                raw = json.dumps(payload).encode()
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):
                path = urlsplit(self.path)
                args = parse_qs(path.query)
                if path.path == '/status':
                    return self.reply(200, device.state())
                if path.path == '/samples':
                    if args['token'][0] != device.token:
                        return self.reply(409, {'protocol':PROTOCOL})
                    if device.poll_failure:
                        return self.reply(503, {'protocol':PROTOCOL})
                    state = device.state()
                    start = max(int(args['after'][0])+1, device.skip)
                    stop = min(state['next_seq'], start+64)
                    if device.kind == 'all':
                        kinds = ('ecg',)*10+('pressure','imu')
                        state['samples'] = [simulated(kinds[i%12], i/250, i) for i in range(start, stop)]
                    else:
                        state['samples'] = [simulated(device.kind, i/250, i) for i in range(start, stop)]
                    if device.wrong_kind and state['samples']:
                        state['samples'][0] = simulated('pressure', start/250, start)
                    return self.reply(200, state)
                self.reply(404, {'protocol':PROTOCOL})

            def do_POST(self):
                args = parse_qs(self.rfile.read(int(self.headers.get('Content-Length', 0))).decode())
                token = args['token'][0]
                if self.path == '/start':
                    if device.running and token != device.token:
                        return self.reply(409, {'protocol':PROTOCOL})
                    device.kind = args['kind'][0]
                    device.token = token
                    device.stream += 1
                    device.started = time.monotonic()
                    device.running = True
                elif self.path == '/stop':
                    if token != device.token:
                        return self.reply(409, {'protocol':PROTOCOL})
                    device.end_seq = device.state()['next_seq']
                    device.running = False
                else:
                    return self.reply(404, {'protocol':PROTOCOL})
                self.reply(200, device.state())

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.address = 'http://127.0.0.1:' + str(self.server.server_port)
        return self

    def __exit__(self, *_):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


class WifiProtocolTests(unittest.TestCase):
    def test_address_validation(self):
        self.assertEqual(normalize_address('192.168.4.1/'), 'http://192.168.4.1')
        for value in ['https://192.168.4.1', 'http://8.8.8.8', 'http://192.168.4.1/start',
                      'http://user:pass@192.168.4.1', 'http://192.168.4.1?x=1']:
            with self.assertRaises(ValueError):normalize_address(value)

    def test_each_module_and_session_ownership(self):
        with VirtualDevice() as server:
            for kind in ('esp32','pressure','imu','ecg'):
                device = WifiDevice(server.address)
                state = device.start(kind)
                self.assertEqual(state['firmware'], 'sensor_wifi_v1')
                with self.assertRaisesRegex(RuntimeError, 'using the ESP32'):
                    WifiDevice(server.address).start(kind)
                time.sleep(.03)
                state, rows = device.poll()
                self.assertGreater(len(rows), 1)
                for row in rows:
                    parse_packet(json.dumps(row), kind)
                    device.acknowledge(row['seq'])
                device.stop()
                self.assertFalse(server.running)

    def test_reboot_rejected(self):
        with VirtualDevice() as server:
            device = WifiDevice(server.address)
            device.start('ecg')
            server.boot = 'different-boot'
            with self.assertRaisesRegex(RuntimeError, 'restarted'):
                device.poll()


class WifiPanelTests(unittest.IsolatedAsyncioTestCase):
    async def capture(self, folder, server, kind='ecg', target=30):
        panel = SensorPanel(kind, folder)
        panel.mode.value = 'WIFI'
        panel.condition.value = '虚拟设备软件验证'
        panel.address.value = server.address
        panel.confirm.value = True
        panel.begin()
        for _ in range(120):
            if len(panel.rows) >= target or panel.task.done():break
            await asyncio.sleep(.025)
        panel.stop_flag = True
        await panel.task
        return panel

    async def test_wifi_without_serial_and_file_provenance(self):
        with VirtualDevice() as server, tempfile.TemporaryDirectory() as folder:
            panel = await self.capture(folder, server)
            self.assertGreaterEqual(len(panel.rows), 30, panel.status.value)
            self.assertEqual(panel.record['capture_error'], '')
            self.assertEqual(panel.record['missing_sequences'], 0)
            self.assertEqual(panel.record['transport'], 'WIFI')
            self.assertEqual(panel.record['source'], 'DEVICE')
            self.assertEqual(panel.record['sample_count'], server.end_seq)
            self.assertEqual(panel.record['device_identity']['device_id'], 'virtual-device')
            self.assertEqual(panel.record['ecg_analysis']['algorithm'], 'ecg_segments_v1')
            self.assertTrue(panel.saved_path.exists())
            self.assertFalse(server.running)
            self.assertNotIn(server.address, DEVICE_OWNERS)
            with panel.saved_path.open(encoding='utf-8-sig') as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(len(rows), len(panel.rows))
            self.assertTrue(all(row['source']=='DEVICE' and row['transport']=='WIFI' for row in rows))
            saved_metadata=json.loads(panel.saved_path.with_suffix('.json').read_text())
            self.assertEqual(saved_metadata['ecg_analysis']['sample_count'],len(rows))

    async def test_initial_missing_samples_reported(self):
        with VirtualDevice() as server, tempfile.TemporaryDirectory() as folder:
            server.skip = 3
            panel = await self.capture(folder, server)
            self.assertEqual(panel.record['missing_sequences'], 3)
            self.assertEqual(panel.rows[0]['seq'], 3)

    async def test_connection_failure_never_falls_back_to_simulation(self):
        with VirtualDevice() as server, tempfile.TemporaryDirectory() as folder:
            server.poll_failure = True
            panel = await self.capture(folder, server)
            self.assertEqual(panel.rows, [])
            self.assertIn('HTTP 503', panel.record['capture_error'])
            self.assertEqual(panel.record['source'], 'DEVICE')
            self.assertFalse(server.running)
            self.assertNotIn(server.address, DEVICE_OWNERS)
            self.assertTrue(panel.saved_path.exists())

    async def test_wireless_preflight_does_not_start_sampling(self):
        with VirtualDevice() as server, tempfile.TemporaryDirectory() as folder:
            panel = SensorPanel('ecg', folder)
            panel.address.value = server.address
            await panel._check_wifi()
            self.assertIn('virtual-device', panel.status.value)
            self.assertFalse(server.running)
            self.assertIsNone(panel.record)

    async def test_real_wifi_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as folder:
            panel = SensorPanel('ecg', folder)
            panel.mode.value = 'WIFI'
            panel.condition.value = '软件检查'
            panel.begin()
            self.assertIsNone(panel.task)

    async def test_wrong_sensor_packet_is_rejected_and_retained_as_error(self):
        with VirtualDevice() as server, tempfile.TemporaryDirectory() as folder:
            server.wrong_kind = True
            panel = await self.capture(folder, server)
            self.assertEqual(panel.rows, [])
            self.assertEqual(panel.record['bad_lines'], 1)
            self.assertIn('pressure', panel.record['capture_error'])
            self.assertTrue(panel.record['invalid_line_examples'])
            self.assertFalse(server.running)

    async def test_sync_page_accepts_three_real_kinds_without_actuation(self):
        with VirtualDevice() as server, tempfile.TemporaryDirectory() as folder:
            server.firmware = 'sensor_sync_v1'
            panel = CombinedPanel(folder)
            panel.mode.value = 'WIFI'
            panel.activity.value = '静坐自然呼吸'
            panel.address.value = server.address
            panel.confirm.value = True
            panel.begin()
            for _ in range(100):
                if len(panel.rows) >= 100 or panel.task.done():
                    break
                await asyncio.sleep(.025)
            panel.stop_flag = True
            await panel.task
            self.assertEqual(panel.record['capture_error'], '')
            self.assertEqual({r['kind'] for r in panel.rows}, {'ecg','pressure','imu'})
            self.assertEqual(panel.record['candidate_analysis']['actuator_command'], None)
            self.assertFalse(panel.record['airbag_bridge_status']['wearable_actuation_permitted'])
            self.assertIsNone(panel.record['candidate_analysis']['joint_observation'])
            self.assertTrue(panel.saved_path.exists())
            self.assertFalse(server.running)

    async def test_sync_bench_auto_rejects_incomplete_capture(self):
        with VirtualDevice() as server, tempfile.TemporaryDirectory() as folder:
            server.firmware = 'sensor_sync_v1'
            panel = CombinedPanel(folder)
            panel.mode.value = 'WIFI'
            panel.activity.value = '静坐自然呼吸'
            panel.address.value = server.address
            panel.confirm.value = True
            panel.controller_port.options = [('虚拟独立板','/dev/fake-uno')]
            panel.bench_confirm.value = True
            panel.bench_auto.value = True
            panel.begin()
            for _ in range(100):
                if len(panel.rows) >= 100 or panel.task.done():
                    break
                await asyncio.sleep(.025)
            panel.stop_flag = True
            await panel.task
            self.assertEqual(panel.record['airbag_event']['result'],'NOT_TRIGGERED')
            self.assertIn('No trigger for this recording',panel.airbag_status.value)
            self.assertTrue(panel.saved_path.exists())

    async def test_continuous_monitor_starts_next_capture_without_another_click(self):
        with tempfile.TemporaryDirectory() as folder, patch('combined_panel.CAPTURE_SECONDS', .12):
            panel = CombinedPanel(folder)
            panel.activity.value = '静坐自然呼吸'
            panel.continuous.value = True
            panel.begin()
            await panel.task
            first_capture = panel.record['capture_id']
            for _ in range(60):
                if panel.record['capture_id'] != first_capture:
                    break
                await asyncio.sleep(.02)
            self.assertNotEqual(panel.record['capture_id'],first_capture)
            panel.request_stop()
            if panel.task and not panel.task.done():
                await panel.task
            self.assertFalse(panel.continuous.value)

    async def test_sync_page_rejects_old_firmware(self):
        with VirtualDevice() as server, tempfile.TemporaryDirectory() as folder:
            panel = CombinedPanel(folder)
            panel.mode.value = 'WIFI'
            panel.activity.value = '静坐自然呼吸'
            panel.address.value = server.address
            panel.confirm.value = True
            panel.begin()
            await panel.task
            self.assertIn('08_sensor_sync', panel.record['capture_error'])
            self.assertEqual(panel.rows, [])
            self.assertFalse(server.running)


if __name__ == '__main__':
    unittest.main()
