"""Three-channel capture and an optional nonhuman bench output path."""
import asyncio
import html
import json
import time
from datetime import datetime

from candidate_rules import analyze_synchronous
from airbag_bridge import auto_bench_permit, current_candidate_status, send_bench_pulse
from wifi_transport import DEFAULT_ADDRESS, WifiDevice, normalize_address
from ui_language import canonical_activity, fit_english_labels

CAPTURE_SECONDS = 20.0


class CombinedPanel:
    def __init__(self, root):
        import ipywidgets as W
        from pathlib import Path
        self.root = Path(root)
        self.rows = []
        self.record = None
        self.saved_path = None
        self.task = None
        self.stop_flag = False
        self.archive_failed = False
        self.participant = W.Text(value='P01', description='Participant ID')
        self.activity = W.Combobox(value='', options=['Seated, natural breathing','Standing, natural breathing','Slow walking'], description='Actual activity',
                                   placeholder='Select or enter the actual activity.', ensure_option=False)
        self.rest = W.Checkbox(value=False, description='Adult at rest throughout: seated or standing quietly. Do not select while walking.', indent=False)
        self.polarity = W.Dropdown(options=[('Positive R peaks',1),('Negative R peaks',-1)], description='ECG peak polarity')
        self.mode = W.Dropdown(options=[('Simulated data','SIMULATED'), ('ESP32 Wi-Fi','WIFI'),
                                        ('ESP32 USB (bench only)','DEVICE')], description='Data source')
        self.address = W.Text(value=DEFAULT_ADDRESS, description='Device address')
        self.port = W.Dropdown(options=[('Click Refresh ports','')], description='Serial port')
        self.refresh = W.Button(description='Refresh ports')
        self.refresh.on_click(self.list_ports)
        self.controller_port = W.Dropdown(options=[('Click Refresh controller ports','')], description='Air-cell Uno')
        self.controller_refresh = W.Button(description='Refresh controller ports')
        self.controller_refresh.on_click(self.list_controller_ports)
        self.bench_confirm = W.Checkbox(value=False, indent=False,
            description='Nonhuman bench only: air cells are not worn, and the controller and air circuit have been checked.')
        self.bench_auto = W.Checkbox(value=False, indent=False,
            description='If any threshold is crossed in this recording, send one 12-cycle bench command to the separate Uno.')
        self.continuous = W.Checkbox(value=False, indent=False,
            description='Continuous monitoring: automatically start the next recording until Stop early is clicked.')
        self.airbag_status = W.HTML('Air-cell bench control is off by default.')
        self.confirm = W.Checkbox(value=False, indent=False,
            description='Wiring and power checked. For body ECG capture, use battery power and Wi-Fi, with USB and charging disconnected.')
        self.start = W.Button(description='Start all channels (about 20 s)', button_style='success')
        self.stop = W.Button(description='Stop early', disabled=True)
        self.start.on_click(self.begin)
        self.stop.on_click(self.request_stop)
        self.review = W.Dropdown(options=[('Pending review','pending'),('Usable for comparison (manual selection)','keep'),
                                          ('Failed attempt','retry')], value='pending', description='Recording result', disabled=True)
        self.notes = W.Textarea(description='Notes', layout=W.Layout(width='100%', height='65px'), disabled=True)
        self.save = W.Button(description='Save result and notes', disabled=True)
        self.save.on_click(self.persist)
        self.status = W.HTML('Simulation is selected by default. Air-cell bench control is off by default.')
        self.result = W.HTML('No capture yet.')
        self.wifi_controls = W.VBox([W.HTML('Connect the Mac to the Wearable- hotspot, then enter the device address. The 08_sensor_sync firmware is required.'), self.address])
        self.usb_controls = W.HBox([self.port, self.refresh])
        self.widget = W.VBox([
            W.HTML('<b>Three-channel observation</b>: intended activities are sitting quietly, standing quietly and walking slowly. Each sensor is analysed separately using the same approximately 20-second recording. Candidate thresholds are not for diagnosis or automatic inflation on a person. Optional linked control is for nonhuman bench use only.'),
            self.participant, self.activity, self.rest, self.polarity, self.mode, self.wifi_controls,
            self.usb_controls, self.confirm,
            W.HTML('<b>Separate air-cell controller (nonhuman bench only)</b>: if any threshold is crossed in a complete approximately 20-second recording, run 12 timed inflation and deflation cycles. Switching on controller power alone does not trigger the updated firmware.'),
            W.HBox([self.controller_port, self.controller_refresh]), self.bench_confirm,
            self.bench_auto, self.continuous, self.airbag_status, W.HBox([self.start, self.stop]),
            self.status, self.result, self.review, self.notes, self.save],
            layout=W.Layout(width='100%'))
        fit_english_labels(self.widget)
        self.mode.observe(self.update_transport, names='value')
        self.update_transport()

    def update_transport(self, _=None):
        self.wifi_controls.layout.display = '' if self.mode.value == 'WIFI' else 'none'
        self.usb_controls.layout.display = '' if self.mode.value == 'DEVICE' else 'none'
        self.confirm.layout.display = '' if self.mode.value != 'SIMULATED' else 'none'

    def list_ports(self, _=None):
        from serial.tools.list_ports import comports
        self.port.options = [(p.device+' '+(p.description or ''),p.device) for p in comports()] or [('No device found','')]

    def list_controller_ports(self, _=None):
        from serial.tools.list_ports import comports
        self.controller_port.options = [(p.device+' '+(p.description or ''),p.device)
                                        for p in comports()] or [('No device found','')]

    def request_stop(self, _=None):
        self.stop_flag = True
        self.continuous.value = False

    async def restart_continuous(self):
        await asyncio.sleep(.1)
        if self.continuous.value and self.task and self.task.done():
            self.begin()

    def begin(self, _=None):
        from lab_suite import DEVICE_OWNERS, capture_identity
        if self.task and not self.task.done():
            return
        if self.archive_failed or (self.record is not None and not self.persist()):
            self.status.value = 'Save the previous recording first.'
            return
        real = self.mode.value != 'SIMULATED'
        if real and not self.confirm.value:
            self.status.value = 'First verify wiring, power and electrical protection for ECG capture.'
            return
        if self.mode.value == 'DEVICE' and not self.port.value:
            self.status.value = 'Select a serial port first.'
            return
        if self.bench_auto.value:
            if self.mode.value == 'SIMULATED':
                self.airbag_status.value = 'Simulated sensor data cannot trigger the air-cell controller.'
                return
            if not self.bench_confirm.value or not self.controller_port.value:
                self.airbag_status.value = 'Confirm nonhuman bench conditions and select the separate air-cell Uno serial port first.'
                return
            if self.mode.value == 'DEVICE' and self.controller_port.value == self.port.value:
                self.airbag_status.value = 'The air-cell Uno and sensor ESP32 must use different serial ports.'
                return
        try:
            device_key = (normalize_address(self.address.value) if self.mode.value == 'WIFI'
                          else self.port.value if real else None)
            if real and device_key in DEVICE_OWNERS:
                self.status.value = 'Another page is capturing from this device. Stop that capture first.'
                return
            self.record = capture_identity(self.root/'data'/'runs', self.participant.value,
                                           canonical_activity(self.activity.value), 'all', 'DEVICE' if real else 'SIMULATED')
        except (ValueError, OSError) as exc:
            self.status.value = html.escape(str(exc))
            return
        self.record['transport'] = self.mode.value
        bench_auto_enabled = bool(self.bench_auto.value)
        controller_port_name = self.controller_port.value if bench_auto_enabled else None
        self.device_key = device_key
        if real:
            DEVICE_OWNERS[device_key] = self
        self.rows = []
        self.saved_path = None
        self.stop_flag = False
        self.airbag_status.value = ('Waiting for the full three-channel recording. Only nonhuman bench operation can be triggered.'
                                    if bench_auto_enabled else 'Air-cell bench control is off for this recording.')
        self.review.value = 'pending'
        self.notes.value = ''
        self.result.value = 'Capturing. Candidate values are calculated after the same approximately 20-second recording finishes.'
        for control in (self.participant,self.activity,self.rest,self.polarity,self.mode,self.address,self.port,self.refresh,self.confirm,
                        self.controller_port,self.controller_refresh,self.bench_confirm,self.bench_auto,self.continuous):
            control.disabled = True
        self.start.disabled = True
        self.stop.disabled = False
        self.review.disabled = True
        self.notes.disabled = False
        self.save.disabled = True
        self.task = asyncio.create_task(self.capture(bench_auto_enabled, controller_port_name))

    async def capture(self, bench_auto_enabled=False, controller_port_name=None):
        import serial
        from lab_suite import BAUD, ALL_DATA_FIELDS, DEVICE_OWNERS, parse_packet, simulated
        mode = self.mode.value
        port = None
        wifi = None
        buffer = b''
        started = time.monotonic()
        last_rx = started
        last_seq = -1
        last_t = -1
        missing = 0
        bad = 0
        bad_examples = []
        error = ''
        firmware = ''
        identity = {}
        selected = False
        last_select = -1
        first_line = True
        overrun = 0
        all_fields = ['v','kind','seq','t_ms']+ALL_DATA_FIELDS+['source','transport','host_elapsed_s']
        def accept(item):
            nonlocal last_seq,last_t,missing,last_rx
            kind = item.get('kind') if isinstance(item, dict) else None
            if kind not in ('pressure','imu','ecg'):
                raise ValueError('Unknown module received during three-channel capture.')
            packet = parse_packet(json.dumps(item), kind)
            if not isinstance(packet['seq'], int) or not isinstance(packet['t_ms'], int):
                raise ValueError('Sequence number or timestamp is not an integer.')
            if packet['seq'] <= last_seq or packet['t_ms'] < last_t:
                raise ValueError('Mixed-stream sequence numbers or timestamps went backwards.')
            missing += packet['seq']-last_seq-1
            last_seq, last_t = packet['seq'], packet['t_ms']
            last_rx = time.monotonic()
            self.rows.append({**dict.fromkeys(all_fields), **packet,
                              'source':'SIMULATED' if mode=='SIMULATED' else 'DEVICE',
                              'transport':mode, 'host_elapsed_s':round(last_rx-started,4)})
            if wifi:
                wifi.acknowledge(packet['seq'])
        try:
            if mode == 'WIFI':
                wifi = WifiDevice(self.device_key)
                state = await asyncio.to_thread(wifi.check)
                firmware = state['firmware']
                if firmware != 'sensor_sync_v1':
                    raise RuntimeError('Three-channel capture requires ESP32 08_sensor_sync firmware.')
                identity = {k:state[k] for k in ('device_id','boot_id')}
                await asyncio.to_thread(wifi.start, 'all')
            elif mode == 'DEVICE':
                port = serial.Serial(self.device_key, BAUD, timeout=0, exclusive=True)
            started = time.monotonic()
            last_rx = started
            next_due = {'ecg':started, 'imu':started, 'pressure':started}
            seq = 0
            while not self.stop_flag and time.monotonic()-started < CAPTURE_SECONDS:
                now = time.monotonic()
                if mode == 'SIMULATED':
                    due = []
                    for kind, interval in (('ecg',.004),('imu',.04),('pressure',.05)):
                        while next_due[kind] <= now:
                            due.append((next_due[kind],kind))
                            next_due[kind] += interval
                    for when,kind in sorted(due):
                        t = when-started
                        item = simulated(kind,t,seq,bpm=75)
                        if kind == 'pressure':
                            import math
                            item['pressure_adc'] = round(1400+700*max(0,math.sin(2*math.pi*t/2))**6)
                        accept(item)
                        seq += 1
                elif mode == 'WIFI':
                    state, raw = await asyncio.to_thread(wifi.poll)
                    overrun = max(overrun, state['sampling_overruns'])
                    for item in raw:
                        accept(item)
                    if not state.get('running'):
                        raise RuntimeError('The ESP32 stopped this capture.')
                    if not raw and now-last_rx > 6:
                        raise RuntimeError('No new data for more than 6 seconds.')
                else:
                    if not selected and now-started-last_select >= .5:
                        port.write(b'SELECT all\n')
                        last_select = now-started
                    buffer += port.read(min(port.in_waiting,32768))
                    if len(buffer) > 8192:
                        raise RuntimeError('Serial data line is too long.')
                    while b'\n' in buffer:
                        line,buffer = buffer.split(b'\n',1)
                        if not line.strip():
                            continue
                        marker = b'# selected all firmware=sensor_sync_v1'
                        if not selected and marker in line:
                            selected = True
                            firmware = 'sensor_sync_v1'
                            continue
                        if first_line and not line.startswith((b'{',b'#')):
                            first_line = False
                            continue
                        first_line = False
                        if line.startswith(b'#'):
                            if b'# error all ' in line:
                                raise RuntimeError(line.decode('utf-8',errors='replace')[:200])
                            continue
                        if selected:
                            try:
                                accept(json.loads(line))
                            except (ValueError, UnicodeError):
                                bad += 1
                                if len(bad_examples) < 3:
                                    bad_examples.append(line[:240].decode('utf-8',errors='replace'))
                                continue
                    if not selected and now-started > 6:
                        raise RuntimeError('No SELECT all acknowledgement from 08_sensor_sync. Check the board model, firmware and serial port.')
                if int(now-started) != int(now-started-.2):
                    counts = {k:sum(r['kind']==k for r in self.rows) for k in ('pressure','imu','ecg')}
                    self.status.value = (f"{mode} | {now - started:.1f}/{CAPTURE_SECONDS:g} s | pressure {counts['pressure']}, IMU {counts['imu']}, ECG {counts['ecg']} samples")
                await asyncio.sleep(.003 if mode in ('SIMULATED','DEVICE') else .04)
            if wifi:
                state = await asyncio.to_thread(wifi.stop)
                target = state['next_seq']
                for _ in range(130):
                    if wifi.last_seq+1 >= target:
                        break
                    state, raw = await asyncio.to_thread(wifi.poll)
                    if not raw:
                        raise RuntimeError('Remaining Wi-Fi capture buffer is missing.')
                    for item in raw:
                        accept(item)
                if wifi.last_seq+1 < target:
                    raise RuntimeError('Remaining Wi-Fi capture data was not fully read.')
                overrun = max(overrun, state['sampling_overruns'])
        except Exception as exc:
            error = str(exc)
            self.status.value = 'Capture failed: '+html.escape(error)+'; the system will not switch to simulated data automatically.'
        finally:
            if wifi and wifi.stream is not None:
                try:
                    await asyncio.to_thread(wifi.stop)
                except Exception as exc:
                    if not error:
                        error = 'Wi-Fi stop acknowledgement failed: '+str(exc)
            if port:
                try:
                    port.write(b'STOP\n')
                finally:
                    port.close()
            if self.device_key and DEVICE_OWNERS.get(self.device_key) is self:
                DEVICE_OWNERS.pop(self.device_key,None)
            for control in (self.participant,self.activity,self.rest,self.polarity,self.mode,self.address,self.port,self.refresh,self.confirm,
                            self.controller_port,self.controller_refresh,self.bench_confirm,self.bench_auto,self.continuous):
                control.disabled = False
            self.start.disabled = False
            self.stop.disabled = True
            self.review.disabled = False
            self.save.disabled = False
            analysis = analyze_synchronous(self.rows,canonical_activity(self.activity.value),self.rest.value,
                transport_ok=(not error and not bad and not missing and not overrun and not self.stop_flag),
                polarity=self.polarity.value)
            self.record.update(ended_at=datetime.now().astimezone().isoformat(timespec='seconds'),
                sample_count=len(self.rows), requested_duration_s=CAPTURE_SECONDS, stop_requested=self.stop_flag,
                bad_lines=bad, missing_sequences=missing, sampling_overruns=overrun,
                invalid_line_examples=bad_examples,
                capture_error=error, firmware=firmware, device_identity=identity,
                ecg_polarity=self.polarity.value, candidate_analysis=analysis,
                airbag_bridge_status=current_candidate_status(analysis))
            if bench_auto_enabled:
                self.record['airbag_event'] = {'mode':'AUTO_CANDIDATE', 'result':'NOT_TRIGGERED',
                                               'reason':'No valid channel crossed its threshold, or data quality was insufficient.'}
            self.show_analysis(analysis)
            if not error:
                self.status.value = (f'Finished: {len(self.rows)} samples; invalid lines {bad}, missing sequence numbers {missing}, sampling overruns {overrun}. ')
            summary = self.status.value
            saved = self.persist()
            if bench_auto_enabled and saved:
                try:
                    permit = auto_bench_permit(analysis, self.record['source'], True)
                    self.record['airbag_event'] = {'mode':'AUTO_CANDIDATE','result':'PENDING_CONTROLLER',
                                                   'rule_id':permit.rule_id}
                    if not self.persist():
                        raise RuntimeError('The triggering recording could not be saved. No air-cell command will be sent.')
                    result = await asyncio.to_thread(send_bench_pulse, controller_port_name, permit,
                        self.device_key if mode == 'DEVICE' else None)
                    self.record['airbag_event'] = {'mode':'AUTO_CANDIDATE','result':'BENCH_CYCLES_DONE',**result}
                    self.airbag_status.value = 'At least one threshold was crossed. The separate Uno completed 12 bench inflation and deflation cycles.'
                except ValueError as exc:
                    self.airbag_status.value = 'No trigger for this recording: '+html.escape(str(exc))
                except Exception as exc:
                    self.record['airbag_event'] = {'mode':'AUTO_CANDIDATE','result':'FAILED',
                                                   'reason':str(exc)}
                    self.airbag_status.value = 'The air-cell controller did not complete its action: '+html.escape(str(exc))
                self.persist()
            elif bench_auto_enabled:
                self.airbag_status.value = 'Recording could not be saved. No air-cell command will be sent.'
            self.status.value = summary+'<br>'+self.status.value
            if (self.continuous.value and not self.stop_flag and not error and saved
                    and not (bench_auto_enabled and analysis.get('any_observation') is True)):
                asyncio.create_task(self.restart_continuous())

    def show_analysis(self, result):
        def cell(kind, label, unit, digits):
            channel = result['channels'][kind]
            value = channel['value']
            shown = 'Unknown' if value is None else f'{value:.{digits}f} {unit}'
            crossing = 'Candidate threshold crossed' if channel['crossed'] is True else ('Threshold not crossed' if channel['crossed'] is False else 'Not assessed')
            reason = ('; '+html.escape(channel['reason'])) if channel['reason'] else ''
            return f'<li>{label}: {shown}; {crossing}{reason}</li>'
        joint = result['joint_observation']
        joint_text = ('All three thresholds crossed in the same recording (observation only)' if joint is True else
                      'Not all three thresholds crossed' if joint is False else 'Same-recording three-threshold result: unknown')
        joint_reason = ('; '+html.escape(result.get('joint_reason',''))) if joint is None else ''
        any_result = result['any_observation']
        any_text = ('At least one candidate threshold crossed' if any_result is True else
                    'No thresholds crossed' if any_result is False else 'Any-threshold result: unknown')
        self.result.value = ('<b>Whole-recording candidate results</b><ul>'+
            cell('pressure','Pressure pulse rate R (candidate R≥34.7853)','pulses/min',2)+
            cell('imu','IMU combined score Q (candidate Q≥9.15)','',2)+
            cell('ecg','Heart rate HR (adult resting reference HR>100)','BPM',1)+
            '</ul><b>'+any_text+'</b>; '+joint_text+joint_reason+
            '. No diagnosis is made. A single control command can be sent only when nonhuman bench control is separately enabled.')

    def persist(self, _=None):
        from lab_suite import save_capture
        if self.record is None:
            return False
        if self.review.value == 'keep' and not self.rows:
            self.status.value = 'No valid data; this recording cannot be marked Usable for comparison.'
            return False
        try:
            metadata = dict(self.record, review_status=self.review.value, notes=self.notes.value,
                reviewed_at=datetime.now().astimezone().isoformat(timespec='seconds') if self.review.value!='pending' else None)
            self.saved_path = save_capture(self.rows,self.root/'data'/'runs',metadata,self.saved_path)
            self.record = metadata
            self.archive_failed = False
            self.status.value = 'Saved: '+html.escape(str(self.saved_path.relative_to(self.root)))
            return True
        except Exception as exc:
            self.archive_failed = True
            self.status.value = 'Save failed: '+html.escape(str(exc))
            return False
