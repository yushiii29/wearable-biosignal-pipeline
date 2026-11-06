"""ESP32 本地热点 HTTP 接收；只接收设备包，不生成或补齐传感器数据。"""
import ipaddress
import json
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import ProxyHandler, Request, build_opener

PROTOCOL = 'wearable_wifi_v1'
DEFAULT_ADDRESS = 'http://192.168.4.1'
MAX_RESPONSE = 131072


def normalize_address(value):
    """热点使用本地 IPv4；拒绝代理、重定向目标及带凭证/路径的地址。"""
    value = value.strip().rstrip('/')
    if '://' not in value:
        value = 'http://' + value
    parts = urlsplit(value)
    try:
        ip = ipaddress.IPv4Address(parts.hostname or '')
        port = parts.port
    except ValueError as exc:
        raise ValueError('The device address must be a local IPv4 address, for example http://192.168.4.1.') from exc
    if (parts.scheme != 'http' or not (ip.is_private or ip.is_loopback)
            or parts.username or parts.password or parts.path or parts.query or parts.fragment):
        raise ValueError('Enter a local device address, for example http://192.168.4.1.')
    return f'http://{ip}' + (f':{port}' if port else '')


class WifiDevice:
    def __init__(self, address=DEFAULT_ADDRESS, timeout=2):
        self.address = normalize_address(address)
        self.timeout = timeout
        self.token = uuid.uuid4().hex
        # 访问 ESP32 不经过系统 HTTP 代理，也不向别的主机跟随重定向。
        from urllib.request import HTTPRedirectHandler
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        self.opener = build_opener(ProxyHandler({}), NoRedirect())
        self.identity = None
        self.stream = None
        self.last_seq = -1
        self.stats = {}

    def request(self, path, data=None):
        body = urlencode(data).encode('ascii') if data is not None else None
        req = Request(self.address + path, data=body,
                      headers={'Content-Type': 'application/x-www-form-urlencoded'} if body else {})
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                raw = response.read(MAX_RESPONSE + 1)
        except HTTPError as exc:
            if exc.code == 409:
                raise RuntimeError('Another capture is using the ESP32. Stop that capture, or wait about 8 seconds and retry.') from exc
            raise RuntimeError(f'ESP32 returned HTTP {exc.code}; check the firmware version and connection.') from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise RuntimeError('Cannot connect to ESP32. Connect the Mac Wi-Fi to a Wearable- hotspot. Wireless firmware must be uploaded and the device must remain powered. This check does not assess body-signal quality.') from exc
        if len(raw) > MAX_RESPONSE:
            raise ValueError('Device response is too long.')
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise ValueError('The device response is not valid JSON. Check the wireless firmware version.') from exc
        if not isinstance(result, dict) or result.get('protocol') != PROTOCOL:
            raise ValueError('This address does not serve compatible ESP32 wireless capture firmware.')
        return result

    def check(self):
        state = self.request('/status')
        if not all(isinstance(state.get(k), str) and state[k] for k in ('device_id', 'boot_id', 'firmware')):
            raise ValueError('Device identity information is incomplete.')
        return state

    def start(self, kind):
        if kind not in ('esp32', 'pressure', 'imu', 'ecg', 'all'):
            raise ValueError('Unknown capture module.')
        self.identity = self.check()
        # 检查成功之后才开启采集；每次使用新 token，避免重试时重复重置序号。
        state = self.request('/start', {'kind': kind, 'token': self.token})
        self.stream = state.get('stream_id')
        if isinstance(self.stream, bool) or not isinstance(self.stream, int):
            raise ValueError('Invalid device capture ID.')
        self.kind = kind
        self.validate_state(state)
        self.last_seq = -1
        return state

    def validate_state(self, state):
        if (state.get('device_id') != self.identity['device_id']
                or state.get('boot_id') != self.identity['boot_id']
                or state.get('stream_id') != self.stream or state.get('kind') != self.kind):
            raise RuntimeError('The ESP32 restarted or the capture session changed. Capture stopped to avoid mixing recordings.')
        if state.get('error'):
            raise RuntimeError('Board report: ' + str(state['error']))
        for key in ('oldest_seq', 'next_seq', 'sampling_overruns'):
            if isinstance(state.get(key), bool) or not isinstance(state.get(key), int) or state[key] < 0:
                raise ValueError('Invalid device-buffer state: ' + key)
        if state['oldest_seq'] > state['next_seq']:
            raise ValueError('Invalid device-buffer sequence range.')
        self.stats = {k: state[k] for k in ('oldest_seq', 'next_seq', 'sampling_overruns')}

    def poll(self):
        state = self.request('/samples?' + urlencode({'token': self.token, 'after': self.last_seq}))
        self.validate_state(state)
        rows = state.get('samples')
        if not isinstance(rows, list) or len(rows) > 64:
            raise ValueError('Invalid batch of device samples.')
        # 序号只能在上层校验完原始数据后推进，坏包不会被静默吞掉。
        return state, rows

    def acknowledge(self, seq):
        if isinstance(seq, bool) or not isinstance(seq, int) or seq <= self.last_seq:
            raise ValueError('Wi-Fi sample sequence numbers repeated or went backwards.')
        self.last_seq = seq

    def stop(self):
        if self.stream is None:
            return None
        state = self.request('/stop', {'token': self.token})
        self.validate_state(state)
        return state
