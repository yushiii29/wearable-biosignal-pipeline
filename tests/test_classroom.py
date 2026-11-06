import asyncio,csv,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('MPLBACKEND','Agg')
from lab_suite import CONFIG,SensorPanel,simulated,parse_packet,save_records,estimate_bpm
class ProtocolTests(unittest.TestCase):
 def test_all_schemas(self):
  for kind in CONFIG:
   r=simulated(kind,1,1)
   self.assertEqual(parse_packet(json.dumps(r),kind),r)
   with self.assertRaises(ValueError):parse_packet(json.dumps(r),'invalid')
 def test_bad_lines(self):
  for line in ['{}','[]','garbage','{"v":1,"kind":"ecg","seq":0,"t_ms":0,"ecg_adc":NaN}']:
   with self.assertRaises(ValueError):parse_packet(line,'ecg')
 def test_bpm(self):
  for bpm in [45,60,75,120,160]:
   rows=[simulated('ecg',i/250,i,bpm=bpm) for i in range(2500)]
   v,note=estimate_bpm(rows);self.assertIsNotNone(v);self.assertAlmostEqual(v,bpm,delta=1.5)
   for r in rows:r['ecg_adc']=1000
   self.assertIsNone(estimate_bpm(rows)[0])
 def test_csv_provenance(self):
  with tempfile.TemporaryDirectory() as d:
   r=dict(simulated('pressure',0,0),source='SIMULATED',host_elapsed_s=0)
   p=save_records([r],d)
   with p.open(encoding='utf-8-sig') as f:data=list(csv.DictReader(f))
   self.assertEqual(data[0]['source'],'SIMULATED')
class PanelTests(unittest.IsolatedAsyncioTestCase):
 async def test_start_stop_save_all(self):
  with tempfile.TemporaryDirectory() as d:
   for kind in CONFIG:
    p=SensorPanel(kind,d);p.condition.value='软件模拟检查';p.begin()
    for _ in range(150):
     if len(p.rows)>3 or p.task.done():break
     await asyncio.sleep(.04)
    p.stop_flag=True;await p.task
    self.assertGreater(len(p.rows),1);self.assertFalse(p.start.disabled);self.assertTrue(p.stop.disabled)
    self.assertTrue(all(r['source']=='SIMULATED' for r in p.rows));p.persist()
    self.assertIn('Saved',p.status.value)
 async def test_real_mode_requires_confirmation(self):
  p=SensorPanel('pressure','.');p.mode.value='DEVICE';p.begin();self.assertIsNone(p.task)
 async def test_serial_transport_with_pty(self):
  # 仅用虚拟串口检查收包，不代表硬件实测。
  with tempfile.TemporaryDirectory() as d:
   master,slave=os.openpty()
   baud_patch=patch("lab_suite.BAUD",115200);baud_patch.start() # macOS伪终端不支持USB设备的非标准460800速率
   try:
    p=SensorPanel('pressure',d);p.condition.value='虚拟串口检查';p.mode.value='DEVICE';p.confirm.value=True
    port=os.ttyname(slave);p.port.options=[port];p.port.value=port;p.begin()
    for _ in range(150):
     if p.connected or p.task.done():break
     await asyncio.sleep(.04)
    self.assertTrue(p.connected,p.status.value)
    os.write(master,(json.dumps(simulated('pressure',0,0))+'\n').encode());await asyncio.sleep(.02)
    os.write(master,b'bad json\n')
    for i in range(1,8):
     os.write(master,(json.dumps(simulated('pressure',i*.05,i))+'\n').encode());await asyncio.sleep(.02)
    await asyncio.sleep(.2);p.stop_flag=True;await p.task
    self.assertEqual(len(p.rows),8,p.status.value);self.assertTrue(all(r['source']=='DEVICE' for r in p.rows))
    self.assertIn('invalid lines 1',p.status.value)
   finally:baud_patch.stop();os.close(master);os.close(slave)
if __name__=='__main__':unittest.main()
