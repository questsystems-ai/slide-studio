#!/usr/bin/env python3
"""
slide-studio local save server.
Serves the project directory, accepts POST /save to write edits back to disk,
proxies POST /api/claude → Anthropic API (key stays server-side),
and manages project folders under the user-chosen workspace directory.

Usage:
    python serve.py
    Open: http://localhost:8500/studio.html   ← workshop (local only)
          http://localhost:8500/index.html    ← dad pitch (mirrors Vercel)
"""
import os
import re
import json
import datetime
import urllib.request
import urllib.error
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = 8500
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDIO_CONFIG_PATH = os.path.join(BASE_DIR, '.studio-config.json')

# ── Load .env.local ────────────────────────────────────────────────────────
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
ANTHROPIC_KEY  = ENV.get('ANTHROPIC_API_KEY', '')
ELEVENLABS_KEY = ENV.get('ELEVENLABS_API_KEY', '')
SUPABASE_URL   = ENV.get('SUPABASE_URL', '')
SUPABASE_ANON  = ENV.get('SUPABASE_ANON_KEY', '')

# ── Load .studio-config.json (workspace dir persists across restarts) ──────
def load_studio_config():
    if os.path.exists(STUDIO_CONFIG_PATH):
        with open(STUDIO_CONFIG_PATH, encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_studio_config(cfg):
    with open(STUDIO_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2)

_studio_cfg = load_studio_config()
WORKSPACE_DIR = _studio_cfg.get('workspaceDir', '')  # empty = not yet chosen

# ── Startup banner ─────────────────────────────────────────────────────────
if ANTHROPIC_KEY:
    print(f'  Anthropic key loaded ({ANTHROPIC_KEY[:12]}...)')
else:
    print('  WARNING: No ANTHROPIC_API_KEY in .env.local — /api/claude will fail')

if SUPABASE_URL:
    print(f'  Supabase: {SUPABASE_URL}')
else:
    print('  INFO: No SUPABASE_URL — auth bypassed in studio.html')

if WORKSPACE_DIR:
    print(f'  Workspace: {WORKSPACE_DIR}')
else:
    print('  INFO: No workspace set — user will be prompted to choose a folder')


# ── Open native folder-picker dialog (tkinter, runs synchronously) ─────────
def pick_folder_dialog(initial_dir=None):
    """Opens a native OS folder picker. Returns path string or '' if cancelled."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes('-topmost', True)
        path = filedialog.askdirectory(
            title='Choose your slide-studio workspace folder',
            initialdir=initial_dir or os.path.expanduser('~')
        )
        root.destroy()
        return path or ''
    except Exception as e:
        print(f'  folder picker error: {e}')
        return ''


AGENT_MEMORY_SEED = """\
# slide-studio Agent Memory

## Presentation Style
- Narration: under 60 words per slide, conversational, direct, first-person or second-person
- One clear idea per slide — don't pack two concepts into one
- Title slide first, conclusion or call-to-action last
- 6–10 slides is the sweet spot for most explainers

## Visual Descriptions
- Be specific: "animated DNA helix rotating, labels appear one by one"
- Flag when a real image is needed: "photograph of PCR thermocycler machine"
- Suggest layout: "split screen — diagram left, key text right"
- If the user said to include images, mark slides that need them with imageRequired: true

## Scoping Question Guidance
- Science/technical topics: ask about discovery history, technical depth, audience level
- Business/pitch topics: ask about audience familiarity, whether to include metrics, call to action
- How-to/process topics: ask about step count, whether visuals per step are wanted
- Always ask about images unless the user already said yes or no
- 3–5 questions max — don't over-scope

## Slide Count Guidelines
- "Quick" or "high-level": 5–7 slides
- "Full explainer": 8–12 slides
- "Deep dive": 12–16 slides
"""

def _seed_agent_memory(workspace_dir):
    mem_dir = os.path.join(workspace_dir, 'agent-memory')
    os.makedirs(mem_dir, exist_ok=True)
    ctx_path = os.path.join(mem_dir, 'context.md')
    if not os.path.exists(ctx_path):
        with open(ctx_path, 'w', encoding='utf-8') as f:
            f.write(AGENT_MEMORY_SEED)
        print(f'  seeded agent-memory/context.md')

# Seed on startup if workspace already set
if WORKSPACE_DIR:
    _seed_agent_memory(WORKSPACE_DIR)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == '/api/config':
            self._handle_config()
        elif self.path == '/api/projects':
            self._handle_list_projects()
        elif self.path == '/api/agent-memory':
            self._handle_agent_memory()
        elif self.path.startswith('/api/conversation/'):
            self._handle_get_conversation()
        elif self.path == '/api/project-images':
            self._handle_list_images()
        elif self.path.startswith('/api/images/'):
            self._handle_serve_image()
        elif self.path.startswith('/api/elevenlabs-voices'):
            self._handle_elevenlabs_voices()
        elif self.path.startswith('/api/screenshot'):
            self._handle_screenshot()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == '/save':
            self._handle_save()
        elif self.path == '/api/claude':
            self._handle_claude()
        elif self.path == '/api/projects/new':
            self._handle_new_project()
        elif self.path == '/api/choose-folder':
            self._handle_choose_folder()
        elif self.path == '/api/set-workspace':
            self._handle_set_workspace()
        elif self.path.startswith('/api/conversation/'):
            self._handle_save_conversation()
        elif self.path.startswith('/api/upload-image'):
            self._handle_upload_image()
        else:
            self.send_response(404)
            self.end_headers()

    # ── /api/config ────────────────────────────────────────────────────────
    def _handle_config(self):
        self._json_ok({
            'supabaseUrl':     SUPABASE_URL,
            'supabaseAnonKey': SUPABASE_ANON,
            'workspaceDir':    WORKSPACE_DIR,
        })

    # ── /api/choose-folder — opens native OS dialog ────────────────────────
    def _handle_choose_folder(self):
        path = pick_folder_dialog(initial_dir=WORKSPACE_DIR or None)
        if path:
            self._json_ok({'path': path, 'cancelled': False})
        else:
            self._json_ok({'path': '', 'cancelled': True})

    # ── /api/set-workspace — saves chosen path to .studio-config.json ──────
    def _handle_set_workspace(self):
        global WORKSPACE_DIR, _studio_cfg
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
        except Exception:
            self._json_error(400, 'Invalid JSON')
            return
        path = data.get('path', '').strip()
        if not path or not os.path.isdir(path):
            self._json_error(400, 'Not a valid directory')
            return
        WORKSPACE_DIR = path
        _studio_cfg['workspaceDir'] = path
        save_studio_config(_studio_cfg)
        _seed_agent_memory(path)
        print(f'  workspace set: {path}')
        self._json_ok({'workspaceDir': path})

    # ── /api/agent-memory — app knowledge + workspace memory ─────────────
    def _handle_agent_memory(self):
        chunks = []
        # 1. App-level knowledge (agent-knowledge/ next to serve.py) — always loaded
        knowledge_dir = os.path.join(BASE_DIR, 'agent-knowledge')
        if os.path.isdir(knowledge_dir):
            for fn in sorted(os.listdir(knowledge_dir)):
                if fn.endswith('.md') or fn.endswith('.txt'):
                    with open(os.path.join(knowledge_dir, fn), encoding='utf-8') as f:
                        chunks.append(f'### [system] {fn}\n{f.read()}')
        # 2. Workspace memory (user-editable, per-installation)
        mem_dir = os.path.join(WORKSPACE_DIR, 'agent-memory') if WORKSPACE_DIR else ''
        if mem_dir and os.path.isdir(mem_dir):
            for fn in sorted(os.listdir(mem_dir)):
                if fn.endswith('.md') or fn.endswith('.txt'):
                    with open(os.path.join(mem_dir, fn), encoding='utf-8') as f:
                        chunks.append(f'### [workspace] {fn}\n{f.read()}')
        self._json_ok({'content': '\n\n'.join(chunks)})

    # ── /api/projects ──────────────────────────────────────────────────────
    def _handle_list_projects(self):
        if not WORKSPACE_DIR or not os.path.isdir(WORKSPACE_DIR):
            self._json_ok([])
            return
        projects = []
        for slug in sorted(os.listdir(WORKSPACE_DIR)):
            proj_path = os.path.join(WORKSPACE_DIR, slug)
            if not os.path.isdir(proj_path):
                continue
            meta_path = os.path.join(proj_path, 'project.json')
            if os.path.exists(meta_path):
                with open(meta_path, encoding='utf-8') as f:
                    try:
                        meta = json.load(f)
                    except Exception:
                        meta = {'slug': slug, 'name': slug, 'scenes': []}
            else:
                meta = {'slug': slug, 'name': slug, 'scenes': []}
            projects.append(meta)
        self._json_ok(projects)

    # ── /api/projects/new ──────────────────────────────────────────────────
    def _handle_new_project(self):
        if not WORKSPACE_DIR:
            self._json_error(400, 'No workspace set — choose a folder first')
            return
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
        except Exception:
            self._json_error(400, 'Invalid JSON')
            return

        name = data.get('name', '').strip()
        if not name:
            self._json_error(400, 'Project name required')
            return

        slug = re.sub(r'[^a-z0-9-]', '-', name.lower())
        slug = re.sub(r'-+', '-', slug).strip('-')
        if not slug:
            self._json_error(400, 'Could not derive a valid slug from that name')
            return

        proj_dir = os.path.join(WORKSPACE_DIR, slug)
        if os.path.exists(proj_dir):
            self._json_error(409, f'A project named "{slug}" already exists')
            return

        os.makedirs(proj_dir)
        os.makedirs(os.path.join(proj_dir, 'audio'))
        os.makedirs(os.path.join(proj_dir, 'svgs'))
        os.makedirs(os.path.join(proj_dir, 'images'))

        meta = {
            'name': name,
            'slug': slug,
            'createdAt': datetime.datetime.utcnow().isoformat() + 'Z',
            'scenes': []
        }
        with open(os.path.join(proj_dir, 'project.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2)

        meta['path'] = proj_dir
        self._json_ok(meta, status=201)
        print(f'  created project: {proj_dir}')

    # ── /api/conversation/<slug> GET/POST ──────────────────────────────────
    def _handle_get_conversation(self):
        slug = self.path.split('/')[-1]
        if not slug or not WORKSPACE_DIR:
            self._json_ok({'messages': [], 'intent': '', 'stage': 'new'})
            return
        path = os.path.join(WORKSPACE_DIR, slug, 'conversation.json')
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                self._json_ok(json.load(f))
        else:
            self._json_ok({'messages': [], 'intent': '', 'stage': 'new', 'lastActive': ''})

    def _handle_save_conversation(self):
        slug = self.path.split('/')[-1]
        if not slug or not WORKSPACE_DIR:
            self._json_error(400, 'No slug or workspace')
            return
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
        except Exception:
            self._json_error(400, 'Invalid JSON')
            return
        proj_dir = os.path.join(WORKSPACE_DIR, slug)
        os.makedirs(proj_dir, exist_ok=True)
        path = os.path.join(proj_dir, 'conversation.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        self._json_ok({'saved': True})

    # ── /api/project-images — list images in workspace/images/ ────────────
    def _handle_list_images(self):
        images_dir = os.path.join(WORKSPACE_DIR, 'images') if WORKSPACE_DIR else ''
        images = []
        if images_dir and os.path.isdir(images_dir):
            exts = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'}
            for fn in sorted(os.listdir(images_dir)):
                if os.path.splitext(fn)[1].lower() in exts:
                    images.append({'filename': fn, 'url': f'/api/images/{fn}'})
        self._json_ok(images)

    # ── /api/upload-image ──────────────────────────────────────────────────
    def _handle_upload_image(self):
        if not WORKSPACE_DIR:
            self._json_error(400, 'No workspace set')
            return
        filename = os.path.basename(self.headers.get('X-Filename', 'image.jpg').strip())
        if not filename:
            self._json_error(400, 'Invalid filename')
            return
        images_dir = os.path.join(WORKSPACE_DIR, 'images')
        os.makedirs(images_dir, exist_ok=True)
        length = int(self.headers.get('Content-Length', 0))
        data = self.rfile.read(length)
        filepath = os.path.join(images_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(data)
        url = f'/api/images/{filename}'
        self._json_ok({'filename': filename, 'url': url, 'size': len(data)})
        print(f'  uploaded image: {filepath}')

    # ── /api/images/<filename> — serve image from workspace/images/ ────────
    def _handle_serve_image(self):
        # path is /api/images/<filename>
        parts = self.path.lstrip('/').split('/', 2)  # ['api','images','filename']
        if len(parts) < 3:
            self.send_response(404); self.end_headers(); return
        filename = os.path.basename(parts[2])
        filepath = os.path.join(WORKSPACE_DIR, 'images', filename)
        if not os.path.isfile(filepath):
            self.send_response(404); self.end_headers(); return
        ext = os.path.splitext(filename)[1].lower()
        mime = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
                '.gif': 'image/gif', '.webp': 'image/webp', '.svg': 'image/svg+xml'}.get(ext, 'application/octet-stream')
        with open(filepath, 'rb') as f:
            data = f.read()
        self.send_response(200)
        self._cors()
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ── /save ──────────────────────────────────────────────────────────────
    def _handle_save(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8')
        filename = self.headers.get('X-Filename', 'presentation.html')
        # Allow subdirectory saves within BASE_DIR but block path traversal
        filename = os.path.normpath(filename).lstrip('/\\')
        if '..' in filename.split(os.sep):
            self._json_error(400, 'Invalid path')
            return
        filepath = os.path.join(BASE_DIR, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(body)
        self.send_response(200)
        self._cors()
        self.end_headers()
        self.wfile.write(b'saved')
        print(f'  saved {filename}')

    # ── /api/screenshot ────────────────────────────────────────────────────
    def _handle_screenshot(self):
        """
        GET /api/screenshot?url=<url>&slide=<n>&width=1280&height=720
        Uses Playwright (headless Chromium) to capture a screenshot.
        Returns JSON: { "path": "<saved file path>", "url": "<served URL>" }
        Screenshots saved to <workspace>/screenshots/
        """
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(self.path).query)
        target_url = (qs.get('url', [''])[0]) or 'http://localhost:8500/studio.html'
        width  = int(qs.get('width',  ['1280'])[0])
        height = int(qs.get('height', ['720'])[0])

        # Save into workspace/screenshots/ or fallback to app dir
        base = WORKSPACE_DIR if WORKSPACE_DIR else BASE_DIR
        out_dir = os.path.join(base, 'screenshots')
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        out_path = os.path.join(out_dir, f'screenshot-{ts}.png')

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self._json({'error': 'Playwright not installed. Run: pip install playwright && python -m playwright install chromium'})
            return

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width': width, 'height': height})
                page.goto(target_url, wait_until='networkidle', timeout=15000)
                page.screenshot(path=out_path, full_page=False)
                browser.close()
            import base64
            with open(out_path, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode()
            print(f'screenshot saved: {out_path}')
            self._json({'path': out_path, 'filename': os.path.basename(out_path), 'base64': b64})
        except Exception as e:
            self._json({'error': str(e)})

    # ── /api/elevenlabs-voices ─────────────────────────────────────────────
    def _handle_elevenlabs_voices(self):
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(self.path).query)
        gender = (qs.get('gender', [''])[0] or '').lower()  # 'male' | 'female'

        if not ELEVENLABS_KEY:
            self._json({'voice_id': None, 'name': None, 'error': 'No ELEVENLABS_API_KEY configured'})
            return

        try:
            req = urllib.request.Request(
                'https://api.elevenlabs.io/v1/voices',
                headers={'xi-api-key': ELEVENLABS_KEY, 'Accept': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
        except Exception as e:
            self._json({'voice_id': None, 'name': None, 'error': str(e)})
            return

        voices = data.get('voices', [])

        # Prefer voices whose labels match the requested gender
        def score(v):
            labels = {k.lower(): str(val).lower() for k, val in (v.get('labels') or {}).items()}
            gender_match = labels.get('gender', '') == gender if gender else True
            # Prefer 'conversational' or 'narration' use_case
            use = labels.get('use_case', '')
            use_score = 2 if use in ('narration', 'conversational') else (1 if use else 0)
            return (int(gender_match) * 10) + use_score

        ranked = sorted(voices, key=score, reverse=True)
        pick = ranked[0] if ranked else None

        if pick:
            self._json({'voice_id': pick['voice_id'], 'name': pick['name']})
        else:
            self._json({'voice_id': None, 'name': None, 'error': 'No voices found'})

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
        self.send_header('Access-Control-Allow-Headers',
                         'Content-Length, Content-Type, X-Filename')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')

    def _json_ok(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self._cors()
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(body)

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


print(f'slide-studio -> http://localhost:{PORT}/studio.html  (workshop)')
print(f'             -> http://localhost:{PORT}/index.html   (dad pitch)')
print('Ctrl+C to stop\n')
HTTPServer(('localhost', PORT), Handler).serve_forever()
