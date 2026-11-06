"""多传感器原型分步验证；所有默认运行均为模拟数据。"""
import asyncio, csv, html, json, math, random, time, io, re, uuid
from datetime import datetime
from pathlib import Path
import numpy as np
from wifi_transport import WifiDevice, DEFAULT_ADDRESS, normalize_address
from ecg_analysis import analyze_ecg, format_ecg_analysis
from ui_language import canonical_activity, fit_english_labels

CONFIG = {
 'esp32': ('ESP32 communication', 10, ['counter']),
 'pressure': ('Pressure sensor', 20, ['pressure_adc']),
 'imu': ('IMU motion', 50, ['ax_g','ay_g','az_g','gx_dps','gy_dps','gz_dps','mx_ut','my_ut','mz_ut','air_pressure_pa']),
 'ecg': ('ECG signal', 250, ['ecg_adc']),
}
ALL_DATA_FIELDS = ['pressure_adc','ax_g','ay_g','az_g','gx_dps','gy_dps','gz_dps',
                   'mx_ut','my_ut','mz_ut','air_pressure_pa','ecg_adc']
BAUD = 460800
RECORD_FOLDERS = {'pending':'待确认', 'keep':'可用于比较', 'retry':'失败尝试'}
DEVICE_OWNERS = {}

class PacketKindMismatch(ValueError):
    def __init__(self, actual, expected):
        self.actual = str(actual)
        super().__init__(f'The board is sending {self.actual}, but this tab expects {expected}')

def filename_label(value):
    """保留中文标签，移除文件路径与通配符字符。"""
    label = re.sub(r'[^\w\-\u4e00-\u9fff]+', '-', value.strip()).strip('-_')
    return label.encode('utf-8')[:48].decode('utf-8', errors='ignore')

def capture_identity(folder, participant, condition, kind, source):
    participant = participant.strip()
    condition = condition.strip()
    if not filename_label(participant) or not filename_label(condition):
        raise ValueError('Enter the participant ID and the actual condition or activity.')
    prefix = f'{filename_label(participant)}_{filename_label(condition)}_{kind}_{source}_尝试'
    attempts = []
    for path in Path(folder).rglob(prefix+'*.csv'):
        match = re.match(re.escape(prefix)+r'(\d+)_', path.name)
        # 文件名过长时只缩短显示标签，完整人员与状态仍保存在记录中。
        sidecar = path.with_suffix('.json')
        if sidecar.exists():
            try:
                previous = json.loads(sidecar.read_text(encoding='utf-8'))
            except (ValueError,OSError):
                previous = None
            if previous and (previous.get('participant_id'),previous.get('condition')) != (participant,condition):
                continue
        if match: attempts.append(int(match.group(1)))
    return {
        'participant_id':participant, 'condition':condition, 'kind':kind, 'source':source,
        'attempt':max(attempts, default=0)+1,
        'capture_id':datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'_'+uuid.uuid4().hex[:8],
        'started_at':datetime.now().astimezone().isoformat(timespec='seconds'),
    }

def save_capture(rows, folder, metadata, previous_path=None):
    """同一次采集更新同一个文件；人工分类后移动至相应目录。"""
    folder = Path(folder)/RECORD_FOLDERS[metadata['review_status']]
    folder.mkdir(parents=True, exist_ok=True)
    stem = (f"{filename_label(metadata['participant_id'])}_{filename_label(metadata['condition'])}_{metadata['kind']}_{metadata['source']}_尝试{metadata['attempt']:03d}_{metadata['capture_id']}")
    path = folder/(stem+'.csv')
    labels = {key:metadata[key] for key in
              ['participant_id','condition','attempt','capture_id','started_at','review_status','notes']}
    data_fields = ALL_DATA_FIELDS if metadata['kind']=='all' else CONFIG[metadata['kind']][2]
    fields = list(rows[0]) if rows else ['v','kind','seq','t_ms']+data_fields+['source','host_elapsed_s']
    fields += [key for key in labels if key not in fields]
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerows(dict(row, **labels) for row in rows)
    # 用临时文件替换，避免保存中断留下半份 CSV。
    csv_tmp = path.with_suffix('.csv.tmp')
    json_tmp = path.with_suffix('.json.tmp')
    csv_tmp.write_text(buffer.getvalue(), encoding='utf-8-sig')
    json_tmp.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    csv_tmp.replace(path)
    json_tmp.replace(path.with_suffix('.json'))
    if previous_path is not None and Path(previous_path) != path:
        Path(previous_path).unlink(missing_ok=True)
        Path(previous_path).with_suffix('.json').unlink(missing_ok=True)
    return path

def simulated(kind, t, seq, control=50, bpm=75):
    rng = random.Random(seq)
    r = {'v':1,'kind':kind,'seq':seq,'t_ms':round(t*1000)}
    if kind == 'esp32': r['counter'] = seq
    elif kind == 'pressure': r['pressure_adc'] = min(4095,max(0,round(control/100*3500+200+rng.gauss(0,8))))
    elif kind == 'imu':
        a=control/100
        r.update(ax_g=a*math.sin(t*8),ay_g=a*.5*math.sin(t*5),az_g=1+a*.2*math.cos(t*8),
                 gx_dps=a*80*math.sin(t*8),gy_dps=a*40*math.cos(t*5),gz_dps=a*20*math.sin(t*4),
                 mx_ut=20+a*math.sin(t),my_ut=5,mz_ut=35,air_pressure_pa=101325)
    elif kind == 'ecg':
        phase=(t*bpm/60)%1
        pulse=lambda center,width:math.exp(-.5*((phase-center)/width)**2)
        r['ecg_adc']=round(1700+1000*pulse(.4,.018)-200*pulse(.36,.015)-300*pulse(.44,.018)+130*pulse(.2,.04)+220*pulse(.65,.06)+rng.gauss(0,8))
    return r

def parse_packet(line, kind):
    """严格校验协议，拒绝其他传感器、缺失值和非有限数字。"""
    if len(line)>4096: raise ValueError('Data line is too long.')
    r=json.loads(line)
    if not isinstance(r,dict) or r.get('v')!=1: raise ValueError('Protocol version mismatch.')
    if r.get('kind')!=kind: raise PacketKindMismatch(r.get('kind'),kind)
    keys=['seq','t_ms']+CONFIG[kind][2]
    for k in keys:
        v=r.get(k)
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v): raise ValueError('Invalid field: '+k)
    if r['seq']<0 or r['t_ms']<0: raise ValueError('Negative timestamp or sequence number.')
    for k in ['pressure_adc','ecg_adc']:
        if k in r and not 0<=r[k]<=4095: raise ValueError('ADC value is out of range.')
    return {k:r[k] for k in ['v','kind']+keys}

def save_records(rows, folder):
    if not rows: raise ValueError('No data yet.')
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    p=folder/f"{rows[0]['kind']}_{rows[0]['source']}_{datetime.now():%Y%m%d_%H%M%S_%f}.csv"
    fields=list(rows[0])
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    return p

def estimate_bpm(rows, polarity=1):
    """兼容旧入口；详细窗口、候选峰和质量说明由 analyze_ecg 提供。"""
    result=analyze_ecg(rows,polarity)
    return result['bpm'],format_ecg_analysis(result)

class SensorPanel:
    def __init__(self,kind,root):
        import ipywidgets as W
        self.W=W;self.kind=kind;self.root=Path(root);self.rows=[];self.task=None;self.stop_flag=False;self.connected=False
        self.record=None;self.saved_path=None;self.archive_failed=False
        self.participant=W.Text(value='P01',description='Participant ID',placeholder='e.g. P01')
        self.condition=W.Combobox(value='',options=['Seated, natural breathing','Standing, natural breathing','Slow walking'],description='Condition / activity',placeholder='Enter the actual condition; custom text is allowed.',ensure_option=False)
        self.record_info=W.HTML('Version: 2026-11-01 USB / Wi-Fi with segment-based heart-rate estimation. Recordings are automatically saved as Pending review when capture ends.')
        self.review=W.Dropdown(options=[('Pending review','pending'),('Usable for comparison (manual selection)','keep'),('Retry / exclude from comparison','retry')],value='pending',description='Recording result',disabled=True)
        self.record_notes=W.Textarea(description='Recording notes',placeholder='After capture starts, note loose contact, sensor position, fit, or other observations.',disabled=True,layout=W.Layout(width='100%',height='65px'))
        self.mode=W.Dropdown(options=[('Simulation: ready to use','SIMULATED'),('Real device: USB serial','DEVICE'),('Real device: Wi-Fi, battery powered','WIFI')],description='Data source')
        self.port=W.Dropdown(options=[('Click Refresh ports first','')],description='Serial port')
        self.refresh=W.Button(description='Refresh ports');self.refresh.on_click(self.list_ports)
        self.address=W.Text(value=DEFAULT_ADDRESS,description='Device address')
        self.wifi_check=W.Button(description='Check Wi-Fi');self.wifi_check.on_click(self.check_wifi)
        self.wifi_info=W.HTML('Upload wireless firmware before first use. Connect the Mac to the Wearable- hotspot using password Wearable2026. Capture works without internet, and the local Jupyter address stays the same. Do not connect USB or charge the battery while body electrodes are connected.')
        self.wifi_controls=W.VBox([self.wifi_info,W.HBox([self.address,self.wifi_check])])
        self.usb_controls=W.HBox([self.port,self.refresh])
        self.confirm=W.Checkbox(description='Model, wiring and power checked; electrical isolation confirmed for body ECG capture.',value=False,indent=False)
        self.duration=W.IntSlider(value=10,min=5,max=60,description='Duration (s)')
        self.control=W.IntSlider(value=20,min=0,max=100,description='Simulated pressure' if kind=='pressure' else 'Simulated motion')
        self.bpm=W.IntSlider(value=75,min=45,max=160,description='Simulated HR')
        self.polarity=W.Dropdown(options=[('Positive R peaks',1),('Negative R peaks',-1)],description='Peak polarity')
        self.start=W.Button(description='Start capture',button_style='success');self.stop=W.Button(description='Stop',disabled=True)
        self.save=W.Button(description='Save result and notes',disabled=True)
        self.start.on_click(self.begin);self.stop.on_click(lambda _:setattr(self,'stop_flag',True));self.save.on_click(self.persist)
        self.status=W.HTML('No capture yet. Simulation is selected by default; no device will be connected.');self.out=W.Image(format='png',layout=W.Layout(width='100%',height='auto'));self.note=W.HTML()
        details={'esp32':'This tests communication with the controller. It is not a fourth sensor.','pressure':'The pressure slider generates simulated numbers only. Real readings are uncalibrated and must not be treated as pressure units or breathing measurements.',
                 'imu':'Shows three-axis acceleration, angular velocity, magnetic field and atmospheric pressure. Motion changes do not diagnose numbness, stiffness or tremor. IMU atmospheric pressure is not the chest film-sensor pressure.',
                 'ecg':'The raw ECG is fully preserved. Heart rate is estimated from the whole recording first; if interference occurs, an estimable segment is used and its time range is shown. Simulated heart rate applies only to simulation mode and is not a measured result.'}
        controls=[W.HTML('<b>'+CONFIG[kind][0]+'</b>: '+details[kind]),
                  W.HTML('Switching modules: stop the current capture before selecting and starting another module. Each device captures one module at a time. Wireless firmware also supports USB.'),
                  self.participant,self.condition,self.record_info,self.mode,self.usb_controls,self.wifi_controls,self.confirm,self.duration]
        if kind in ['pressure','imu']:controls.append(self.control)
        if kind=='ecg':controls.extend([self.bpm,self.polarity])
        controls += [W.HBox([self.start,self.stop]),self.status,self.out,self.note,self.review,self.record_notes,self.save]
        self.widget=W.VBox(controls,layout=W.Layout(width='100%'))
        fit_english_labels(self.widget)
        self.mode.observe(self.update_transport,names='value')
        self.update_transport()
    def update_transport(self,_=None):
        self.usb_controls.layout.display='' if self.mode.value=='DEVICE' else 'none'
        self.wifi_controls.layout.display='' if self.mode.value=='WIFI' else 'none'
        if self.mode.value=='WIFI':
            self.status.value='Wi-Fi capture has not started. Connect the Mac to the ESP32 hotspot, then click Check Wi-Fi.'
        elif self.mode.value=='DEVICE':
            self.status.value='USB capture has not started. Refresh and select a serial port; keep body electrode leads disconnected.'
        else:self.status.value='No capture yet. Simulation generates data in software without connecting to a device.'
    def check_wifi(self,_=None):
        if self.task and not self.task.done():return
        if getattr(self,'wifi_check_task',None) and not self.wifi_check_task.done():return
        self.wifi_check_task=asyncio.create_task(self._check_wifi())
    async def _check_wifi(self):
        self.wifi_check.disabled=True
        try:
            state=await asyncio.to_thread(WifiDevice(self.address.value).check)
            self.status.value=html.escape(f"Connected to real ESP32: {state['device_id']} | {state['firmware']}. Only Wi-Fi communication has been confirmed. Capture has not started, and ECG signal quality has not been verified.")
        except Exception as exc:self.status.value='Wi-Fi connection check failed: '+html.escape(str(exc))
        finally:self.wifi_check.disabled=False
    def list_ports(self,_=None):
        from serial.tools.list_ports import comports
        ports=[(p.device+' '+(p.description or ''),p.device) for p in comports()]
        self.port.options=ports or [('No device found; simulation does not need a port.','')]
    def begin(self,_=None):
        if self.task and not self.task.done():return
        # 开始下一轮前，将上一轮尚未点击保存的分类与备注补写到原文件。
        if self.record is not None and not self.archive_failed:
            if not self.persist():return
        if self.archive_failed:
            self.status.value='The previous recording was not saved successfully. Click Save result and notes to retry before continuing, so no data is lost.';return
        real=self.mode.value!='SIMULATED'
        if real and not self.confirm.value:
            self.status.value='Device capture has not started. First verify wiring, power and electrical protection for body-connected use.';return
        if self.mode.value=='DEVICE' and not self.port.value:
            self.status.value='USB capture has not started. Refresh and select a serial port.';return
        try:device_key=normalize_address(self.address.value) if self.mode.value=='WIFI' else self.port.value
        except ValueError as exc:self.status.value=html.escape(str(exc));return
        owner=DEVICE_OWNERS.get(device_key) if real else None
        if owner is not None and owner is not self:
            self.status.value='Another module is using this device. Stop that module before starting this one.';return
        try:
            source='SIMULATED' if not real else 'DEVICE'
            record=capture_identity(self.root/'data'/'runs',self.participant.value,canonical_activity(self.condition.value),self.kind,source)
        except (ValueError,OSError) as exc:
            self.status.value=html.escape(str(exc));return
        self.record=record;self.saved_path=None
        self.capture_port=self.port.value
        self.capture_device_key=device_key
        self.capture_address=device_key if self.mode.value=='WIFI' else None
        self.record['transport']='WIFI' if self.mode.value=='WIFI' else 'USB' if real else 'SIMULATED'
        if real:DEVICE_OWNERS[device_key]=self
        self.review.value='pending';self.review.disabled=True;self.record_notes.value='';self.record_notes.disabled=False
        self.participant.disabled=True;self.condition.disabled=True
        self.record_info.value=html.escape(f"{record['participant_id']} | {record['condition']} | {self.kind} | Attempt {record['attempt']:03d}")
        self.rows=[];self.stop_flag=False;self.connected=False;self.start.disabled=True;self.stop.disabled=False;self.save.disabled=True;self.mode.disabled=True
        for control in (self.address,self.wifi_check,self.port,self.refresh,self.confirm,self.duration,self.polarity):control.disabled=True
        self.note.value='';self.task=asyncio.create_task(self.capture())
    async def capture(self):
        import serial
        import matplotlib.pyplot as plt
        from IPython.display import display
        mode=self.mode.value;source='SIMULATED' if mode=='SIMULATED' else 'DEVICE'
        start=time.monotonic();last_draw=0;last_rx=start;port=None;wifi=None;buffer=b'';bad=0;missing=0;last_seq=None;last_t=None;capture_error=''
        wireless_state={};wireless_stop_error='';device_identity={}
        other_kinds={};diagnostics=[];bad_examples=[];startup_fragments=[];first_frame=True;last_select=-1;firmware='unknown'
        hz=CONFIG[self.kind][1];limit=self.duration.value
        fields={'esp32':['counter'],'pressure':['pressure_adc'],'imu':['ax_g','ay_g','az_g'],'ecg':['ecg_adc']}[self.kind]
        with plt.ioff():fig,ax=plt.subplots(figsize=(7,2.6))
        lines=[ax.plot([],[],label=f)[0] for f in fields];ax.set_xlabel('Device / simulation time (s)');ax.set_title(source+' / '+self.kind);ax.legend(loc='upper right');ax.grid(alpha=.2)
        def redraw():
            buffer=io.BytesIO();fig.tight_layout();fig.savefig(buffer,format='png',dpi=110)
            self.out.value=buffer.getvalue()
        redraw()
        def accept_packets(packets,now):
            nonlocal bad,missing,last_seq,last_t,last_rx
            for r in packets:
                if last_seq is not None and (r['seq']<=last_seq or r['t_ms']<=last_t):
                    if mode=='WIFI':raise ValueError('Wi-Fi sequence numbers or timestamps repeated or went backwards. Capture stopped.')
                    bad+=1;continue
                if last_seq is not None:missing+=max(0,r['seq']-last_seq-1)
                elif mode=='WIFI':missing+=r['seq']
                last_seq=r['seq'];last_t=r['t_ms'];last_rx=now
                self.rows.append(dict(r,source=source,transport=self.record['transport'],host_elapsed_s=round(now-start,4)))
        def wireless_packets(raw):
            nonlocal bad
            packets=[]
            for item in raw:
                try:
                    r=parse_packet(json.dumps(item),self.kind)
                    if not isinstance(r['seq'],int) or not isinstance(r['t_ms'],int):raise ValueError('Wi-Fi sequence numbers or timestamps are not integers.')
                    wifi.acknowledge(r['seq'])
                except ValueError:
                    bad+=1
                    if len(bad_examples)<3:bad_examples.append(json.dumps(item,ensure_ascii=False)[:240])
                    raise
                packets.append(r)
            return packets
        try:
            if mode=='DEVICE':port=serial.Serial(self.capture_port,BAUD,timeout=0,exclusive=True)
            elif mode=='WIFI':
                wifi=WifiDevice(self.capture_address)
                wireless_state=await asyncio.to_thread(wifi.start,self.kind)
                firmware=wifi.identity['firmware']
                device_identity={k:wifi.identity[k] for k in ('device_id','boot_id')}
            self.connected=True;start=time.monotonic();last_rx=start
            seq=0
            while not self.stop_flag and time.monotonic()-start<limit:
                now=time.monotonic();packets=[]
                if mode=='SIMULATED':
                    packets=[simulated(self.kind,seq/hz,seq,self.control.value,self.bpm.value)];seq+=1
                elif mode=='WIFI':
                    wireless_state,raw=await asyncio.to_thread(wifi.poll)
                    packets=wireless_packets(raw)
                    if not wireless_state.get('running'):raise RuntimeError('The ESP32 stopped this capture. Check the connection and start again.')
                    if not packets and now-last_rx>6:raise RuntimeError('No new data for more than 6 seconds. Wi-Fi capture stopped.')
                else:
                    # 打开串口可能重启 ESP32；在首条匹配数据到达前重发选择命令。
                    if not self.rows and now-start-last_select>=.5:
                        port.write(f'SELECT {self.kind}\n'.encode('ascii'))
                        last_select=now-start
                    chunk=port.read(min(port.in_waiting,32768))
                    buffer+=chunk
                    while b'\n' in buffer:
                        line,buffer=buffer.split(b'\n',1)
                        if not line.strip():continue
                        # 串口刚打开时可能截到启动残片，后接完整的固件确认行。
                        # 只恢复已知确认标记；残片另存，不能把其他格式错误隐藏掉。
                        markers=[f'# selected {self.kind} firmware={v}'.encode('ascii') for v in ('sensor_switch_v1','sensor_wifi_v1','sensor_sync_v1')]
                        marker_at=max(line.find(marker) for marker in markers)
                        if not self.rows and marker_at>0:
                            startup_fragments=(startup_fragments+[line[:marker_at].hex()])[-3:]
                            line=line[marker_at:]
                        if first_frame:
                            first_frame=False
                            # 打开正在发送的串口可能从一行中途开始；只对首行做边界恢复。
                            if not line.startswith((b'{',b'#')):
                                startup_fragments=(startup_fragments+[line[:240].hex()])[-3:]
                                continue
                        if line.startswith(b'#'):
                            message=line.decode('utf-8',errors='replace')[:240]
                            diagnostics=(diagnostics+[message])[-8:]
                            if 'sensor_switch_v1' in message:firmware='sensor_switch_v1'
                            if 'sensor_wifi_v1' in message:firmware='sensor_wifi_v1'
                            if 'sensor_sync_v1' in message:firmware='sensor_sync_v1'
                            if message.startswith(f'# error {self.kind} '):
                                raise RuntimeError('Board report: '+message[2:])
                            continue
                        try:packets.append(parse_packet(line.decode('utf-8'),self.kind))
                        except PacketKindMismatch as exc:
                            other_kinds[exc.actual]=other_kinds.get(exc.actual,0)+1
                        except (ValueError,UnicodeError):
                            bad+=1
                            if len(bad_examples)<3:bad_examples.append(line.decode('utf-8',errors='replace')[:240])
                    if len(buffer)>8192:buffer=b'';bad+=1
                    if not self.rows and not packets and now-start>4:
                        if other_kinds:
                            raise RuntimeError('The board is still sending '+', '.join(other_kinds)+'; upload arduino/05_sensor_switch/05_sensor_switch.ino, then restart the kernel to use the updated page.')
                        if now-start>6:
                            detail=('; '+diagnostics[-1]) if diagnostics else ''
                            raise RuntimeError('No valid data received for this module. Check the serial port, firmware and wiring.'+detail)
                accept_packets(packets,time.monotonic())
                if now-last_draw>=.5:
                    last_draw=now
                    shown=self.rows[-(1250 if self.kind=='ecg' else 3000):]
                    if shown:
                        x=[r['t_ms']/1000 for r in shown]
                        for line,f in zip(lines,fields):line.set_data(x,[r[f] for r in shown])
                        ax.relim();ax.autoscale_view()
                        redraw()
                    warning='; waiting for '+self.kind+' data' if mode!='SIMULATED' and not self.rows else ('; data interrupted, check the connection' if now-last_rx>3 else '')
                    self.status.value=f"{source} / {self.record['transport']} | {len(self.rows)} samples | invalid lines {bad} | missing sequence numbers {missing}"+warning
                await asyncio.sleep(max(0,start+seq/hz-time.monotonic()) if mode=='SIMULATED' else (.005 if mode=='DEVICE' or len(packets)==64 else .08))
            if wifi:
                # 先停止设备，再读完已采集的尾部；不让最后一批留在板上丢失。
                wireless_state=await asyncio.to_thread(wifi.stop)
                target=wireless_state['next_seq']
                for _ in range(20):
                    if wifi.last_seq+1>=target:break
                    wireless_state,raw=await asyncio.to_thread(wifi.poll)
                    if not raw:raise RuntimeError('Buffered data is missing after the device stopped; the recording tail is incomplete.')
                    accept_packets(wireless_packets(raw),time.monotonic())
                if wifi.last_seq+1<target:raise RuntimeError('Could not finish reading the remaining Wi-Fi buffer.')
            if self.rows:
                shown=self.rows[-(1250 if self.kind=='ecg' else 3000):]
                for line,f in zip(lines,fields):line.set_data([r['t_ms']/1000 for r in shown],[r[f] for r in shown])
                ax.relim();ax.autoscale_view();redraw()
            span=(self.rows[-1]['t_ms']-self.rows[0]['t_ms'])/1000 if len(self.rows)>1 else 0
            rate=(len(self.rows)-1)/span if span>0 else 0
            self.status.value=f"Stopped: {source} / {self.record['transport']}, total {len(self.rows)} samples; effective rate {rate:.1f} Hz; invalid lines {bad}, missing sequence numbers {missing}. "
            if startup_fragments:self.status.value+=f' Startup fragments: {len(startup_fragments)} (saved separately).'
            if self.kind=='imu' and self.rows:
                a=np.array([[r[f] for f in fields] for r in self.rows]);self.note.value=f'Acceleration magnitude standard deviation: {np.std(np.linalg.norm(a, axis=1)):.4f} g (a motion-variation feature, not a symptom assessment)'
        except Exception as exc:
            capture_error=str(exc)
            self.status.value='Capture failed: '+html.escape(capture_error)+'. The system will not switch to simulated data automatically.'
        finally:
            self.connected=False
            if wifi and wifi.stream is not None:
                try:await asyncio.to_thread(wifi.stop)
                except Exception as exc:
                    wireless_stop_error=str(exc)
                    if not capture_error:
                        capture_error='Wi-Fi stop acknowledgement failed: '+wireless_stop_error
                        self.status.value+=' Stop acknowledgement failed. The ESP32 stops automatically after about 8 seconds without a receiver connection.'
            if port:
                try:port.write(b'STOP\n')  # 06 支持停止；05 忽略，不影响兼容。
                finally:port.close()
            if mode!='SIMULATED' and DEVICE_OWNERS.get(self.capture_device_key) is self:
                DEVICE_OWNERS.pop(self.capture_device_key,None)
            plt.close(fig);self.start.disabled=False;self.stop.disabled=True;self.mode.disabled=False
            self.participant.disabled=False;self.condition.disabled=False
            for control in (self.address,self.wifi_check,self.port,self.refresh,self.confirm,self.duration,self.polarity):control.disabled=False
            self.review.disabled=False;self.save.disabled=False
            span=(self.rows[-1]['t_ms']-self.rows[0]['t_ms'])/1000 if len(self.rows)>1 else 0
            self.record.update(ended_at=datetime.now().astimezone().isoformat(timespec='seconds'),
                               sample_count=len(self.rows),duration_s=span,
                               effective_hz=(len(self.rows)-1)/span if span>0 else 0,
                               bad_lines=bad,missing_sequences=missing,capture_error=capture_error,
                               requested_duration_s=limit,stop_requested=self.stop_flag,
                               other_module_packets=other_kinds,device_diagnostics=diagnostics,
                               invalid_line_examples=bad_examples,startup_fragments_hex=startup_fragments,firmware=firmware,
                               device_identity=device_identity,wireless_statistics=wifi.stats if wifi else {},
                               wireless_address=self.capture_address,wireless_stop_error=wireless_stop_error)
            if self.kind=='ecg':
                # 所有原始样本照常保存，质量标记只限制解释，不删除动作片段。
                # 即便采集中途失败，也对已收到的样本单独留分析结果。
                try:
                    analysis=analyze_ecg(self.rows,self.polarity.value)
                    self.note.value=html.escape(format_ecg_analysis(analysis,source))
                    self.record['ecg_analysis']=analysis
                except Exception as exc:
                    self.note.value='Heart-rate analysis failed; raw data is still preserved: '+html.escape(str(exc))
                    self.record['ecg_analysis']={'status':'analysis_failed','error':str(exc)}
            summary=self.status.value
            self.persist()
            self.status.value=summary+'<br>'+self.status.value
    def persist(self,_=None):
        if self.task and not self.task.done() and self.connected:return False
        if self.record is None:
            self.status.value='No capture yet.';return False
        if self.review.value=='keep' and not self.rows:
            self.status.value='This recording has no valid data and cannot be marked Usable for comparison. Select Pending review or Retry / exclude.';return False
        try:
            metadata=dict(self.record,review_status=self.review.value,notes=self.record_notes.value,
                          reviewed_at=datetime.now().astimezone().isoformat(timespec='seconds') if self.review.value!='pending' else None)
            path=save_capture(self.rows,self.root/'data'/'runs',metadata,self.saved_path)
            self.record=metadata;self.saved_path=path;self.archive_failed=False
            self.status.value='Saved: '+html.escape(str(path.relative_to(self.root)))
            if self.review.value=='pending':
                self.status.value+='<br>This recording is still Pending review. Select its result, enter notes, then click Save result and notes.'
            return True
        except Exception as exc:
            self.archive_failed=True
            self.status.value='Save failed. Retry before starting another capture: '+html.escape(str(exc))
            return False

def project_dashboard(root=None):
    # The notebook may have remained open while the bench bridge changed.
    # Refresh its imported modules whenever a new dashboard is built.
    import importlib
    import candidate_rules, airbag_bridge, combined_panel
    for module in (candidate_rules, airbag_bridge, combined_panel):
        importlib.reload(module)
    import ipywidgets as W
    from combined_panel import CombinedPanel
    root=Path(root or Path.cwd());panels=[SensorPanel(k,root) for k in ('esp32','pressure','imu','ecg')]
    panels.append(CombinedPanel(root))
    tab=W.Tab(children=[p.widget for p in panels])
    for i,k in enumerate(('esp32','pressure','imu','ecg')):tab.set_title(i,CONFIG[k][0])
    tab.set_title(4,'Three-channel observation')
    tab._panels=panels
    tab._capture_help='Single-sensor tabs capture one module at a time. The three-channel tab requires 08_sensor_sync firmware and records all channels for about 20 seconds to observe candidate threshold crossings only.'
    return tab
