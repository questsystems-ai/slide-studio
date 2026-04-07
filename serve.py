#!/usr/bin/env python3
"""
slide-studio local save server.
Serves the project directory, accepts POST /save to write edits back to disk,
and proxies POST /api/claude → Anthropic API (key stays server-side).

Usage:
    python serve.py
    Open: http://localhost:8500/index.html
"""
import os
import json
import urllib.request
import urllib.error
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = 8500
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load .env.local
def load_env():
    env_path = os.path.join(BASE_DIR, '.env.local')
    env = {}
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.strip()
    return env

ENV = load_env()
ANTHROPIC_KEY = ENV.get('ANTHROPIC_API_KEY', '')
ELEVENLABS_KEY = ENV.get('ELEVENLABS_API_KEY', '')

if ANTHROPIC_KEY:
    print(f'  Anthropic key loaded ({ANTHROPIC_KEY[:12]}...)')
else:
    print('  WARNING: No ANTHROPIC_API_KEY in .env.local — /api/claude will fail')


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if self.path == '/save':
            self._handle_save()
        elif self.path == '/api/claude':
            self._handle_claude()
        else:
            self.send_response(404)
            self.end_headers()

    # ── /save ──────────────────────────────────────────────────────────────
    def _handle_save(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8')
        filename = self.headers.get('X-Filename', 'presentation.html')
        filename = os.path.basename(filename)
        filepath = os.path.join(BASE_DIR, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(body)
        self.send_response(200)
        self._cors()
        self.end_headers()
        self.wfile.write(b'saved')
        print(f'  saved {filename}')

    # ── /api/claude ────────────────────────────────────────────────────────
    def _handle_claude(self):
        if not ANTHROPIC_KEY:
            self._json_error(500, 'No ANTHROPIC_API_KEY configured')
            return
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        try:
            payload = json.loads(body)
        except Exception:
            self._json_error(400, 'Invalid JSON')
            return

        # Forward to Anthropic
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=json.dumps(payload).encode(),
            headers={
                'x-api-key': ANTHROPIC_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            method='POST'
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = resp.read()
            self.send_response(200)
            self._cors()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(result)
        except urllib.error.HTTPError as e:
            err_body = e.read()
            self.send_response(e.code)
            self._cors()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(err_body)
            print(f'  Anthropic error {e.code}: {err_body[:200]}')
        except Exception as e:
            self._json_error(500, str(e))

    # ── helpers ────────────────────────────────────────────────────────────
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Length, Content-Type, X-Filename')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')

    def _json_error(self, code, msg):
        body = json.dumps({'error': msg}).encode()
        self.send_response(code)
        self._cors()
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        if args and str(args[1]) not in ('200', '304'):
            super().log_message(format, *args)


print(f'slide-studio -> http://localhost:{PORT}/index.html')
print('Ctrl+C to stop\n')
HTTPServer(('localhost', PORT), Handler).serve_forever()
