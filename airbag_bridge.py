"""Computer-to-independent-Uno link for nonhuman bench demonstrations only."""
from dataclasses import dataclass
import time

PROTOCOL = 'AIRBAG_BENCH_V5'
BAUD = 9600
ACTION_TIMEOUT_S = 305


@dataclass(frozen=True)
class BenchPermit:
    """One explicit automatic bench action; never authorizes wearable inflation."""
    rule_id: str = ''
    mode: str = ''
    any_channel_crossed: bool = False
    data_quality_ok: bool = False
    source: str = 'SIMULATED'
    nonhuman_bench_confirmed: bool = False

    def require(self):
        if not self.nonhuman_bench_confirmed:
            raise ValueError('Nonhuman bench conditions have not been confirmed. No air-cell command will be sent.')
        if self.mode != 'AUTO_CANDIDATE':
            raise ValueError('Unknown bench trigger mode. No air-cell command will be sent.')
        if not (self.rule_id == 'candidate_capture_v1' and self.any_channel_crossed
                and self.data_quality_ok and self.source == 'DEVICE'):
            raise ValueError('No valid channel crossed its threshold, or real-device data is invalid. No air-cell command will be sent.')


def auto_bench_permit(analysis, source, nonhuman_bench_confirmed):
    """One complete ~20 s candidate capture, with no extra consecutive-count rule."""
    crossed = (analysis.get('version') == 'candidate_capture_v1'
               and analysis.get('any_observation') is True
               and any(analysis.get('channels', {}).get(k, {}).get('crossed') is True
                       for k in ('pressure', 'imu', 'ecg')))
    permit = BenchPermit(rule_id='candidate_capture_v1', mode='AUTO_CANDIDATE',
                         any_channel_crossed=crossed, data_quality_ok=crossed,
                         source=source, nonhuman_bench_confirmed=nonhuman_bench_confirmed)
    permit.require()
    return permit


def _read_reply(port, prefix, deadline):
    while time.monotonic() < deadline:
        line = port.readline().decode('ascii', errors='replace').strip()
        if line.startswith(prefix):
            return line
        if line.startswith('DENY '):
            raise RuntimeError('Uno rejected the command: '+line)
        if line == 'DONE STOP' and prefix == 'DONE FIRE':
            raise RuntimeError('The Uno action stopped early.')
    raise TimeoutError('The Uno did not return '+prefix+'; execution has not been confirmed.')


def _open_controller(port_name, serial_factory):
    if not port_name:
        raise ValueError('Specify the serial port of the separate Uno/Nano.')
    if serial_factory is None:
        from serial import Serial
        serial_factory = Serial
    port = serial_factory(port_name, BAUD, timeout=.2, write_timeout=1, exclusive=True)
    try:
        # Opening a classic Uno serial port may reset it. Its firmware must boot with all outputs off.
        deadline = time.monotonic()+5
        try:
            _read_reply(port, 'READY '+PROTOCOL, deadline)
        except TimeoutError:
            port.write(b'PING\n')
            _read_reply(port, 'PONG '+PROTOCOL, time.monotonic()+2)
        port.write(b'STATUS\n')
        status = _read_reply(port, 'STATUS '+PROTOCOL, time.monotonic()+2)
        return port, status
    except Exception:
        port.close()
        raise


def check_bench_controller(port_name, serial_factory=None):
    """Read-only identification and output/arm state; never sends FIRE."""
    port, status = _open_controller(port_name, serial_factory)
    port.close()
    return status


def send_bench_pulse(port_name, permit, sensor_port=None, serial_factory=None):
    """Send one bounded 12-cycle bench sequence after a validated decision."""
    permit.require()
    if sensor_port and port_name == sensor_port:
        raise ValueError('The air-cell Uno must use a different serial port from the sensor ESP32.')
    port, status = _open_controller(port_name, serial_factory)
    try:
        fields = dict(part.split('=',1) for part in status.split()[2:] if '=' in part)
        if fields.get('OUTPUTS') != '1' or fields.get('PULSING') != '0':
            raise RuntimeError('Uno bench output is not enabled or an action is still running. FIRE will not be sent.')
        port.write(b'ARM\n')
        _read_reply(port, 'OK ARM', time.monotonic()+2)
        port.write(b'STATUS\n')
        armed_status = _read_reply(port, 'STATUS '+PROTOCOL, time.monotonic()+2)
        if ' ARMED=1 ' not in armed_status or ' PULSING=0' not in armed_status:
            raise RuntimeError('The Uno did not confirm bench enabling for this session. FIRE will not be sent.')
        port.write(b'FIRE\n')
        acknowledged = _read_reply(port, 'OK FIRE', time.monotonic()+2)
        completed = _read_reply(port, 'DONE FIRE', time.monotonic()+ACTION_TIMEOUT_S)
        return {'acknowledged': acknowledged, 'completed': completed,
                'rule_id': permit.rule_id, 'controller_status_before': status}
    finally:
        try:
            port.write(b'STOP\n')
        finally:
            port.close()


def current_candidate_status(analysis):
    """Report the observation separately from the physical bench output state."""
    return {'sensor_joint_observation': analysis.get('joint_observation'),
            'sensor_any_observation': analysis.get('any_observation'),
            'trigger_channels': analysis.get('trigger_channels', []),
            'bench_auto_candidate': analysis.get('any_observation') is True,
            'wearable_actuation_permitted': False,
            'reason': 'Candidate results from the full approximately 20-second recording are for nonhuman bench demonstrations only. Output also requires a separate controller and serial enabling for this session.'}
