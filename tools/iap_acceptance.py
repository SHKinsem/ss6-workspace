"""Bench helper. Secrets are read from platformio.ini and never written to logs.

snapshot/upload/run/capture require an explicitly supplied SS6 host. Upload only
stages bytes; run is the separate, hardware-mutating action. Local timestamps use HK.
"""
import argparse
import configparser
import datetime
import hashlib
import json
import re
from pathlib import Path
import socket
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib

ROOT = Path(__file__).resolve().parents[1]
ZONE = datetime.timezone(datetime.timedelta(hours=8))

def stamp():
    return datetime.datetime.now(ZONE).isoformat(timespec="milliseconds")

def discover():
    name = b''.join(bytes([len(x)]) + x for x in b'_arduino._tcp.local'.split(b'.')) + b'\0'
    query = struct.pack('!6H', 0, 0, 1, 0, 0, 0) + name + struct.pack('!2H', 12, 0x8001)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(.5)
        s.bind(('', 0))
        s.sendto(query, ('224.0.0.251', 5353))
        until = time.monotonic() + 6
        found = set()
        while time.monotonic() < until:
            try:
                data, peer = s.recvfrom(8192)
                if b'ss6' in data.lower(): found.add(peer[0])
            except socket.timeout: pass
    print(json.dumps({'ss6_candidates': sorted(found)}))

class Session:
    def __init__(self, host, out):
        self.base = 'http://' + host
        self.out = Path(out); self.out.mkdir(parents=True, exist_ok=True)
        self.client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read(ROOT / 'repos/ss6-control/platformio.ini', encoding='utf-8')
        self.token = cfg['ota']['password']

    def request(self, path, data=None, headers=None, timeout=12):
        req = urllib.request.Request(self.base + path, data=data, headers=headers or {})
        try:
            with self.client.open(req, timeout=timeout) as r: return r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e: return e.code, e.read(), dict(e.headers)

    def save(self, name, value):
        (self.out / name).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')

    def get(self, path):
        code, raw, _ = self.request(path)
        if code != 200: raise RuntimeError(f'{path}: HTTP {code}: {raw[:200]!r}')
        return json.loads(raw)

    def command(self, line):
        code, raw, _ = self.request('/api/cmd', urllib.parse.urlencode({'line':line}).encode())
        if code != 204: raise RuntimeError(f'command failed: {code}: {raw[:200]!r}')

    def logs(self, label):
        offset, text = 0, ''
        for _ in range(10):
            code, raw, h = self.request(f'/api/log?from={offset}')
            if code != 200: break
            text += raw.decode(errors='replace')
            nxt = int(h.get('X-Log-Next', offset))
            if not raw or nxt == offset: break
            offset = nxt
        text = re.sub(r'\(password [^)]*\)', '(password [REDACTED])', text)
        (self.out / f'{label}-console.log').write_text(stamp()+'\n'+text, encoding='utf-8')

    def snapshot(self, label):
        state = self.get('/api/status')
        if 'motion' in state:
            self.command('stats')
            self.command('errors')
        self.save(label+'-status.json', {'time':stamp(), 'status':state})
        self.logs(label)
        print(json.dumps(state, ensure_ascii=False), flush=True)

    def post(self, action, fields=None):
        code, raw, _ = self.request('/api/iap/'+action, urllib.parse.urlencode(fields or {}).encode(), {'X-IAP-Token':self.token})
        result = {'time':stamp(), 'action':action, 'code':code, 'message':raw.decode(errors='replace')}
        with (self.out / 'actions.jsonl').open('a', encoding='utf-8') as f: f.write(json.dumps(result)+'\n')
        print(json.dumps(result), flush=True)
        if code >= 400: raise RuntimeError(result['message'])

    def upload(self, path, address):
        image = Path(path).read_bytes()
        digest = hashlib.sha256(image).hexdigest()
        catalog = self.get('/api/iap')
        if address not in catalog['addresses']: raise ValueError('address is not configured on this board')
        if not any(i['bytes'] == len(image) and i['sha256'] == digest for i in catalog['images']):
            raise ValueError('image is not in the board full-SHA256 catalog')
        boundary = 'SS6NativeIapAcceptanceUpload'
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="firmware"; filename="vendor.bin"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
                + image + f'\r\n--{boundary}--\r\n'.encode())
        code, raw, _ = self.request('/api/iap/image', body, {'X-IAP-Token':self.token, 'X-IAP-Address':str(address), 'X-IAP-CRC32':f'{zlib.crc32(image):08x}', 'Content-Type':f'multipart/form-data; boundary={boundary}'}, 30)
        result = {'time':stamp(), 'address':address, 'bytes':len(image), 'sha256':digest, 'code':code, 'message':raw.decode(errors='replace')}
        self.save('upload.json', result); print(json.dumps(result), flush=True)
        if code != 200: raise RuntimeError(result['message'])
        status = self.get('/api/iap'); self.save('staged.json', status)
        if not status['ready'] or status['sha256'] != digest or status['address'] != address: raise RuntimeError('board image hash mismatch')

    def run(self, recovery, address, path):
        digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        staged = self.get('/api/iap')
        if not staged['ready'] or staged['address'] != address or staged['sha256'] != digest:
            raise ValueError('staged target/image differs from explicitly requested address/image')
        self.save('before-start-iap.json', staged)
        self.post('start', {'confirm':f'{address}:{digest}', 'recovery':'1' if recovery else '0'})
        start = time.monotonic(); last_print = -10; failures = 0
        with (self.out / 'progress.jsonl').open('a', encoding='utf-8') as log:
            while time.monotonic() - start < 950:
                try:
                    s = self.get('/api/iap'); failures = 0
                    record = {'time':stamp(), 'elapsed':round(time.monotonic()-start,3), **s}
                    log.write(json.dumps(record)+'\n'); log.flush()
                    if record['elapsed'] - last_print >= 5 or s['state'] in ('succeeded','failed'):
                        print(f"{record['elapsed']:.1f}s {s['state']} {s['acknowledged']}/{s['frames']} retries={s['restarts']} capture={s.get('captureCount')} dropped={s.get('captureDropped')} {s['error']}", flush=True)
                        last_print = record['elapsed']
                    if s['state'] in ('succeeded','failed'):
                        self.save('result.json', record); self.capture(); self.snapshot('after-transfer')
                        return s['state'] == 'succeeded'
                except (OSError, ValueError) as e:
                    failures += 1
                    log.write(json.dumps({'time':stamp(),'poll_error':str(e)})+'\n'); log.flush()
                    print(f'poll error ({failures}); do not restart blindly: {e}', flush=True)
                time.sleep(.75)
        raise RuntimeError('monitor deadline exceeded; query state before any further action')

    def capture(self):
        offset = 0
        with (self.out / 'can-capture.csv').open('w', encoding='utf-8') as log:
            log.write('index,uptime_us_mod32,event,id,extended,remote,dlc,data\n')
            while True:
                code, data, h = self.request(f'/api/iap/capture?from={offset}')
                if code != 200: raise RuntimeError(f'capture HTTP {code}')
                nxt = int(h['X-Next']); log.write(data.decode()); log.flush()
                if nxt == offset or nxt >= int(h['X-Count']): break
                offset = nxt
        print('capture saved', flush=True)

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['discover','snapshot','upload','run','capture','release'])
    p.add_argument('--host'); p.add_argument('--out', default='logs/iap-acceptance')
    p.add_argument('--address', type=int); p.add_argument('--image'); p.add_argument('--label', default='snapshot'); p.add_argument('--recovery', action='store_true')
    a = p.parse_args()
    if a.action == 'discover': discover()
    else:
        if not a.host: p.error('--host required')
        if a.action in ('upload', 'run') and (not a.image or a.address is None): p.error('--image and --address required')
        s = Session(a.host,a.out)
        if a.action == 'snapshot': s.snapshot(a.label)
        elif a.action == 'upload': s.upload(a.image,a.address)
        elif a.action == 'run': raise SystemExit(0 if s.run(a.recovery,a.address,a.image) else 1)
        elif a.action == 'capture': s.capture()
        elif a.action == 'release': s.post('release')
