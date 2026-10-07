import json
import os
import random
import string
import urllib.request
import urllib.parse
from datetime import datetime, date
from http.server import BaseHTTPRequestHandler

try:
    from upstash_redis import Redis
except ImportError:
    Redis = None

ADMIN_USER = os.environ.get('ADMIN_USER', 'anish')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'anish123')


def get_redis():
    if Redis is None:
        raise Exception('upstash-redis not installed')
    url = os.environ.get('UPSTASH_REDIS_REST_URL') or os.environ.get('KV_REST_API_URL')
    token = os.environ.get('UPSTASH_REDIS_REST_TOKEN') or os.environ.get('KV_REST_API_TOKEN')
    if not url or not token:
        raise Exception('Redis credentials missing. Set UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN.')
    return Redis(url=url, token=token)


def get_json(r, key, default):
    try:
        val = r.get(key)
        if val is None:
            return default
        return json.loads(val) if isinstance(val, str) else val
    except Exception:
        return default


def set_json(r, key, value):
    r.set(key, json.dumps(value))


def get_keys(r): return get_json(r, 'api_keys', [])
def save_keys(r, v): set_json(r, 'api_keys', v)
def get_logs(r): return get_json(r, 'usage_logs', [])
def save_logs(r, v): set_json(r, 'usage_logs', v)


def next_id(r):
    try:
        return int(r.incr('next_id'))
    except Exception:
        return random.randint(100000, 999999)


def today_str():
    return date.today().isoformat()


class handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _json(self, data, status=200):
        body = json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._json({})

    def do_GET(self):
        try:
            self._handle()
        except Exception as e:
            self._json({'error': str(e)}, 500)

    def do_POST(self):
        try:
            self._handle()
        except Exception as e:
            self._json({'error': str(e)}, 500)

    def _handle(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        body = {}
        if self.command == 'POST':
            length = int(self.headers.get('Content-Length', 0) or 0)
            if length > 0:
                try:
                    raw = self.rfile.read(length).decode('utf-8')
                    body = json.loads(raw) if raw else {}
                except Exception:
                    body = {}

        action = (qs.get('action', [None])[0]) or body.get('action')
        token = (qs.get('token', [None])[0]) or body.get('token') or ''
        auth = self.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            token = auth[7:]
        key = qs.get('key', [None])[0]
        num = qs.get('num', [None])[0]

        r = get_redis()

        if action == 'login':       return self._login(r, body)
        if action == 'logout':      return self._logout(r, token)
        if action == 'list_keys':   return self._list_keys(r, token)
        if action == 'create_key':  return self._create_key(r, token, body)
        if action == 'edit_key':    return self._edit_key(r, token, body)
        if action == 'toggle_key':  return self._toggle_key(r, token, body)
        if action == 'delete_key':  return self._delete_key(r, token, body)
        if action == 'reset_daily': return self._reset_daily(r, token)
        if action == 'stats':       return self._stats(r, token)

        if key or num:
            return self._number(r, key, num)

        self._json({'error': 'Invalid request'}, 400)

    def _check_auth(self, r, token):
        if not token:
            return False
        try:
            return r.exists(f'session:{token}') == 1
        except Exception:
            return False

    def _login(self, r, body):
        user = str(body.get('user', '')).strip()
        pwd = str(body.get('pass', ''))
        if user == ADMIN_USER and pwd == ADMIN_PASS:
            token = ''.join(random.choices(string.ascii_letters + string.digits, k=48))
            try:
                r.set(f'session:{token}', '1', ex=86400)
            except Exception:
                pass
            return self._json({'success': True, 'token': token})
        return self._json({'error': 'Invalid credentials'}, 401)

    def _logout(self, r, token):
        if token:
            try:
                r.delete(f'session:{token}')
            except Exception:
                pass
        return self._json({'success': True})

    def _list_keys(self, r, token):
        if not self._check_auth(r, token):
            return self._json({'error': 'Unauthorized'}, 401)
        keys = get_keys(r)
        logs = get_logs(r)
        today = today_str()
        for k in keys:
            k['used_today'] = sum(1 for l in logs if int(l.get('api_key_id', 0)) == int(k['id']) and str(l.get('used_at', '')).startswith(today))
            k['total_used'] = sum(1 for l in logs if int(l.get('api_key_id', 0)) == int(k['id']))
        return self._json({'keys': keys})

    def _create_key(self, r, token, body):
        if not self._check_auth(r, token):
            return self._json({'error': 'Unauthorized'}, 401)
        key_text = str(body.get('key_text', '')).strip()
        daily_limit = int(body.get('daily_limit', 100) or 0)
        expiry_date = str(body.get('expiry_date', '')).strip()
        if not key_text:
            return self._json({'error': 'Key text required'}, 400)
        keys = get_keys(r)
        if any(k['key_text'] == key_text for k in keys):
            return self._json({'error': 'Key already exists'}, 400)
        new_key = {
            'id': next_id(r),
            'key_text': key_text,
            'service_type': 'number',
            'daily_limit': daily_limit,
            'expiry_date': expiry_date,
            'created_at': datetime.now().isoformat(),
            'active': 1,
        }
        keys.append(new_key)
        save_keys(r, keys)
        return self._json({'success': True, 'key': new_key})

    def _edit_key(self, r, token, body):
        if not self._check_auth(r, token):
            return self._json({'error': 'Unauthorized'}, 401)
        try:
            kid = int(body.get('id', 0))
        except Exception:
            return self._json({'error': 'Invalid ID'}, 400)
        daily_limit = int(body.get('daily_limit', 0) or 0)
        expiry_date = str(body.get('expiry_date', '')).strip()
        keys = get_keys(r)
        found = False
        for k in keys:
            if int(k['id']) == kid:
                k['daily_limit'] = daily_limit
                k['expiry_date'] = expiry_date
                found = True
                break
        if not found:
            return self._json({'error': 'Key not found'}, 404)
        save_keys(r, keys)
        return self._json({'success': True})

    def _toggle_key(self, r, token, body):
        if not self._check_auth(r, token):
            return self._json({'error': 'Unauthorized'}, 401)
        try:
            kid = int(body.get('id', 0))
        except Exception:
            return self._json({'error': 'Invalid ID'}, 400)
        keys = get_keys(r)
        found = False
        for k in keys:
            if int(k['id']) == kid:
                k['active'] = 0 if k.get('active', 1) else 1
                found = True
                break
        if not found:
            return self._json({'error': 'Key not found'}, 404)
        save_keys(r, keys)
        return self._json({'success': True})

    def _delete_key(self, r, token, body):
        if not self._check_auth(r, token):
            return self._json({'error': 'Unauthorized'}, 401)
        try:
            kid = int(body.get('id', 0))
        except Exception:
            return self._json({'error': 'Invalid ID'}, 400)
        keys = [k for k in get_keys(r) if int(k['id']) != kid]
        logs = [l for l in get_logs(r) if int(l.get('api_key_id', 0)) != kid]
        save_keys(r, keys)
        save_logs(r, logs)
        return self._json({'success': True})

    def _reset_daily(self, r, token):
        if not self._check_auth(r, token):
            return self._json({'error': 'Unauthorized'}, 401)
        today = today_str()
        logs = [l for l in get_logs(r) if not str(l.get('used_at', '')).startswith(today)]
        save_logs(r, logs)
        return self._json({'success': True})

    def _stats(self, r, token):
        if not self._check_auth(r, token):
            return self._json({'error': 'Unauthorized'}, 401)
        keys = get_keys(r)
        logs = get_logs(r)
        today = today_str()
        today_count = sum(1 for l in logs if str(l.get('used_at', '')).startswith(today))
        active = sum(1 for k in keys if k.get('active', 1))
        return self._json({
            'total_keys': len(keys),
            'active_keys': active,
            'total_requests': len(logs),
            'today_requests': today_count,
        })

    def _number(self, r, key, num):
        if not key:
            return self._json({
                'error': 'Missing API key',
                'usage': '?key=YOUR_KEY&num=9876543210',
                'BUY_API': '@Vectraen',
                'SUPPORT': '@Vectraen',
            }, 400)

        keys = get_keys(r)
        key_row = None
        for k in keys:
            if k.get('key_text') == key and k.get('service_type', 'number') == 'number' and k.get('active', 1):
                key_row = k
                break
        if not key_row:
            return self._json({'error': 'Invalid API key', 'BUY_API': '@Vectraen', 'SUPPORT': '@Vectraen'}, 401)

        exp = str(key_row.get('expiry_date', '') or '').strip()
        if exp:
            try:
                exp_dt = datetime.strptime(exp, '%Y-%m-%d')
                if exp_dt < datetime.now():
                    return self._json({
                        'error': f"API Key expired on {exp_dt.strftime('%d-%m-%Y')}",
                        'BUY_API': '@Vectraen',
                        'SUPPORT': '@Vectraen',
                    }, 401)
            except Exception:
                pass

        logs = get_logs(r)
        today = today_str()
        used_today = sum(
            1 for l in logs
            if int(l.get('api_key_id', 0)) == int(key_row['id'])
            and str(l.get('used_at', '')).startswith(today)
        )
        limit = int(key_row.get('daily_limit', 100) or 0)
        if limit > 0 and used_today >= limit:
            return self._json({
                'error': f'Daily limit of {limit} reached',
                'BUY_API': '@Vectraen',
                'SUPPORT': '@Vectraen',
            }, 429)

        if not num:
            return self._json({
                'error': 'Missing num parameter',
                'usage': '?key=YOUR_KEY&num=9876543210',
                'BUY_API': '@Vectraen',
                'SUPPORT': '@Vectraen',
            }, 400)

        phone = ''.join(c for c in num if c.isdigit())
        if len(phone) != 10:
            return self._json({
                'error': 'Invalid phone number! Need 10 digits.',
                'BUY_API': '@Vectraen',
                'SUPPORT': '@Vectraen',
            }, 400)

        url = 'https://anishexploits.com/api/number.php?exploits=' + urllib.parse.quote(phone)
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode('utf-8', errors='ignore')
            data = json.loads(raw)
        except Exception as e:
            return self._json({
                'error': f'Upstream error: {e}',
                'BUY_API': '@Vectraen',
                'SUPPORT': '@Vectraen',
            }, 502)

        if isinstance(data, dict) and 'data' in data:
            result = data['data']
        else:
            result = data

        logs.append({
            'api_key_id': int(key_row['id']),
            'query': phone,
            'used_at': datetime.now().isoformat(),
        })
        if len(logs) > 20000:
            logs = logs[-20000:]
        save_logs(r, logs)

        return self._json({
            'username': key_row['key_text'],
            'type': 'number',
            'data': result,
            'BUY_API': '@Vectraen',
            'SUPPORT': '@Vectraen',
        })
