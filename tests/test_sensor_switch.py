"""仅验证协议、虚拟串口切换和文件管理；不代表真实传感器正常。"""
import asyncio
import csv
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('MPLBACKEND','Agg')
from lab_suite import (SensorPanel, PacketKindMismatch, capture_identity,
                       parse_packet, save_capture, simulated)


class RecordTests(unittest.TestCase):
    def test_mismatch_is_distinct(self):
        with self.assertRaises(PacketKindMismatch) as caught:
            parse_packet(json.dumps(simulated('pressure',0,0)),'imu')
        self.assertEqual(caught.exception.actual,'pressure')

    def test_attempts_and_reclassification(self):
        with tempfile.TemporaryDirectory() as folder:
            record=capture_identity(folder,'P01','静坐自然呼吸','pressure','SIMULATED')
            record.update(review_status='pending',notes='第一次')
            rows=[dict(simulated('pressure',0,0),source='SIMULATED',host_elapsed_s=0)]
            path=save_capture(rows,folder,record)
            self.assertEqual(record['attempt'],1)
            record.update(review_status='retry',notes='接触松动')
            new_path=save_capture(rows,folder,record,path)
            self.assertFalse(path.exists())
            self.assertEqual(len(list(Path(folder).rglob('*.csv'))),1)
            self.assertEqual(save_capture(rows,folder,record,new_path),new_path)
            with new_path.open(encoding='utf-8-sig') as f:
                row=next(csv.DictReader(f))
            self.assertEqual(row['notes'],'接触松动')
            self.assertEqual(row['review_status'],'retry')
            self.assertEqual(capture_identity(folder,'P01','静坐自然呼吸','pressure','SIMULATED')['attempt'],2)
            self.assertEqual(capture_identity(folder,'P01','站立自然呼吸','pressure','SIMULATED')['attempt'],1)

    def test_no_data_attempt_retained(self):
        with tempfile.TemporaryDirectory() as folder:
            record=capture_identity(folder,'P01','无数据','imu','DEVICE')
            record.update(review_status='pending',notes='',sample_count=0,capture_error='no data')
            path=save_capture([],folder,record)
            with path.open(encoding='utf-8-sig') as f:
                self.assertEqual(list(csv.DictReader(f)),[])
            self.assertEqual(json.loads(path.with_suffix('.json').read_text())['sample_count'],0)


class SwitchingTests(unittest.IsolatedAsyncioTestCase):
    async def test_commands_and_all_module_parsing(self):
        with tempfile.TemporaryDirectory() as folder:
            master,slave=os.openpty()
            os.set_blocking(master,False)
            commands=[]
            done=False

            async def virtual_firmware():
                buffer=b''
                active='esp32'
                seq=0
                while not done:
                    try:buffer+=os.read(master,4096)
                    except BlockingIOError:pass
                    while b'\n' in buffer:
                        line,buffer=buffer.split(b'\n',1)
                        if line.startswith(b'SELECT '):
                            active=line.decode().split()[1]
                            seq=0
                            commands.append(active)
                            os.write(master,b'\xff\xfe'+f'# selected {active} firmware=sensor_switch_v1\n'.encode())
                    packet=simulated(active,seq*.02,seq)
                    os.write(master,(json.dumps(packet)+'\n').encode())
                    seq+=1
                    await asyncio.sleep(.02)

            fake=asyncio.create_task(virtual_firmware())
            try:
                with patch('lab_suite.BAUD',115200):
                    for kind in ['pressure','imu','ecg','pressure','esp32']:
                        panel=SensorPanel(kind,folder)
                        panel.condition.value='虚拟设备软件检查'
                        panel.mode.value='DEVICE';panel.confirm.value=True
                        panel.port.options=[os.ttyname(slave)]
                        panel.begin()
                        for _ in range(200):
                            if len(panel.rows)>=12 or panel.task.done():break
                            await asyncio.sleep(.025)
                        panel.stop_flag=True
                        await panel.task
                        self.assertGreaterEqual(len(panel.rows),12,panel.status.value)
                        self.assertTrue(all(row['kind']==kind for row in panel.rows))
                        self.assertEqual(panel.record['firmware'],'sensor_switch_v1')
                        self.assertEqual(panel.record['bad_lines'],0)
                        self.assertEqual(panel.record['startup_fragments_hex'],['fffe'])
                        self.assertTrue(panel.saved_path.exists())
                self.assertEqual(commands,['pressure','imu','ecg','pressure','esp32'])
            finally:
                done=True
                await fake
                os.close(master);os.close(slave)


if __name__=='__main__':unittest.main()
