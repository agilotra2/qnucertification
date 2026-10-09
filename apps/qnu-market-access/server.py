"""Loopback-only demo. Demo role selection is NOT production authentication."""
import argparse
import datetime
import hashlib
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import secrets
import threading
from urllib.parse import parse_qs, unquote, urlparse
from pathlib import Path

from engine import APP, Guide, safe_partner
from brief import brief

PUBLIC = {'/': 'index.html', '/app.js': 'app.js', '/styles.css': 'styles.css', '/qnu-logo.svg': 'qnu-logo.svg', '/brief.css': 'brief.css', '/print.js': 'print.js'}
ROLES = {'employee', 'partner', 'admin'}

class DemoServer(ThreadingHTTPServer):
    def __init__(self, address, guide=None):
        if address[0] != '127.0.0.1':
            raise ValueError('This demo may only bind to 127.0.0.1')
        super().__init__(address, Handler)
        self.guide = guide or Guide()
        self.sessions = {}
        self.lock = threading.Lock()

class Handler(BaseHTTPRequestHandler):
    server_version = 'QNuLocalDemo/1'

    def log_message(self, fmt, *args):
        # Do not log query strings or evidence text.
        pass

    def send(self, status, value, kind='application/json; charset=utf-8', filename=None, cookie=None):
        payload = json.dumps(value, ensure_ascii=False).encode() if kind.startswith('application/json') else value.encode() if isinstance(value, str) else value
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store, max-age=0')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if filename:
            self.send_header('Content-Disposition', 'attachment; filename="' + filename + '"')
        if cookie:
            self.send_header('Set-Cookie', 'qnu_demo=' + cookie + '; HttpOnly; SameSite=Strict; Path=/')
        self.end_headers()
        self.wfile.write(payload)

    def host_ok(self):
        port = self.server.server_address[1]
        return self.headers.get('Host') in ('127.0.0.1:' + str(port), 'localhost:' + str(port))

    def session(self):
        try:
            cookie = SimpleCookie(self.headers.get('Cookie', ''))
            token = cookie.get('qnu_demo')
            token = token.value if token else ''
        except Exception:
            return None
        with self.server.lock:
            session = self.server.sessions.get(token)
        return session

    def do_GET(self):
        if not self.host_ok():
            return self.send(403, {'error': 'Local demo host required'})
        url = urlparse(self.path)
        route = unquote(url.path)
        if route in PUBLIC:
            target = APP / 'public' / PUBLIC[route]
            kind = mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
            return self.send(200, target.read_bytes(), kind)
        if route == '/api/session':
            session = self.session()
            if session:
                return self.send(200, {'role': session['role'], 'csrf': session['csrf'], 'demo': True})
            token = secrets.token_urlsafe(32)
            session = {'role': 'employee', 'csrf': secrets.token_urlsafe(32)}
            with self.server.lock:
                self.server.sessions[token] = session
            return self.send(200, {**session, 'demo': True}, cookie=token)
        session = self.session()
        if not session:
            return self.send(401, {'error': 'Demo session required'})
        role = session['role']
        guide = self.server.guide
        qs = parse_qs(url.query)
        args = {k: v[0] for k, v in qs.items()}
        if 'modules' in args:
            args['modules'] = args['modules'].split('|') if args['modules'] else []
        try:
            if route == '/api/catalog':
                return self.send(200, guide.catalog(role))
            if route in ('/api/results', '/api/export', '/brief'):
                result = guide.result(args, role)
                if route == '/brief':
                    return self.send(200, brief(result), 'text/html; charset=utf-8')
                return self.send(200, result, filename='qnu-market-access-' + role + '.json' if route == '/api/export' else None)
            if route == '/api/evidence':
                return self.send(200, guide.evidence(args.get('ref', ''), role))
            if route.startswith('/api/sources/'):
                return self.send(200, guide.source(route.rsplit('/', 1)[1], role))
            if route == '/api/download':
                if role == 'partner':
                    raise PermissionError('Original files are not approved for partner downloads')
                field = {'workbook': 'original_workbook', 'status-csv': 'original_csv'}.get(args.get('file'))
                if not field:
                    raise KeyError('Download not found')
                path = Path(guide.data[field])
                expected = guide.data['workbook_sha256' if field == 'original_workbook' else 'csv_sha256']
                if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                    raise ValueError('Original file changed after import. Stage and review a new dataset before downloading.')
                return self.send(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or 'application/octet-stream', filename='qnu-source' + path.suffix)
            if route == '/api/admin':
                if role != 'admin':
                    raise PermissionError('Administrator demo role required')
                path = APP / 'private/invitations.json'
                candidates = [r for r in guide.data['certifications'] if r['status'] not in ('-', '')]
                return self.send(200, {'invitations': json.loads(path.read_text()) if path.exists() else [], 'approvals': guide.approved_statements(), 'candidates': candidates, 'coverage': guide.data['coverage'], 'version': guide.data['version'], 'notes': 'Local demo drafts only. No email is sent. Publishing here only affects this loopback demo. Source labels are unverified and version scope must be confirmed.'})
            return self.send(404, {'error': 'Route not found'})
        except PermissionError as err:
            return self.send(403, {'error': str(err)})
        except KeyError as err:
            return self.send(404, {'error': str(err)})
        except ValueError as err:
            return self.send(400, {'error': str(err)})

    def do_POST(self):
        if not self.host_ok():
            return self.send(403, {'error': 'Local demo host required'})
        session = self.session()
        if not session:
            return self.send(401, {'error': 'Demo session required'})
        allowed = ('http://127.0.0.1:' + str(self.server.server_address[1]), 'http://localhost:' + str(self.server.server_address[1]))
        if self.headers.get('Origin') not in allowed or self.headers.get('X-CSRF-Token') != session['csrf'] or self.headers.get('Content-Type') != 'application/json':
            return self.send(403, {'error': 'Same-origin JSON request and CSRF token required'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 16000:
                raise ValueError('Invalid body length')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('JSON body must be an object')
            route = urlparse(self.path).path
            if route == '/api/demo-role':
                if body.get('role') not in ROLES:
                    raise ValueError('Invalid role')
                token = secrets.token_urlsafe(32)
                new_session = {'role': body['role'], 'csrf': secrets.token_urlsafe(32)}
                with self.server.lock:
                    old = SimpleCookie(self.headers.get('Cookie'))['qnu_demo'].value
                    self.server.sessions.pop(old, None)
                    self.server.sessions[token] = new_session
                return self.send(200, {**new_session, 'demo': True}, cookie=token)
            if session['role'] != 'admin':
                raise PermissionError('Administrator demo role required')
            guide = self.server.guide
            if route == '/api/admin/invitations':
                import re
                email = body.get('email', '')
                if not isinstance(email, str) or len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or body.get('role') not in ('employee', 'partner'):
                    raise ValueError('Enter an email and intended role')
                path = APP / 'private/invitations.json'
                with self.server.lock:
                    rows = json.loads(path.read_text()) if path.exists() else []
                    rows.append({'id': secrets.token_hex(8), 'email': email, 'role': body['role'], 'state': 'Local draft — not sent; not a login', 'created': datetime.datetime.now(datetime.timezone.utc).isoformat()})
                    path.write_text(json.dumps(rows, indent=2))
                return self.send(201, rows[-1])
            if route == '/api/admin/approvals':
                # No caller-supplied raw data, scope or wording is published. A
                # single reviewed certification statement is the approval unit.
                candidate = next((r for r in guide.data['certifications'] if r['ref'] == body.get('ref') and r['status'] not in ('-', '')), None)
                if not candidate or body.get('confirm') != 'publish-local-demo' or not isinstance(body.get('review_note'), str) or len(body['review_note'].strip()) < 15:
                    raise ValueError('Review a source record and provide a scope/wording review note (15+ characters)')
                statement = {'id': hashlib.sha256((guide.data['version'] + candidate['ref']).encode()).hexdigest()[:16], 'product': candidate['product'], 'text': 'Approved local-demo wording: internal source labels ' + candidate['product'] + ' / ' + candidate['category'] + ' as ' + candidate['status'] + '. This is a source assertion; exact certificate and product-version scope require confirmation. No completion date is asserted.', 'ref': candidate['ref'], 'review_note': body['review_note'].strip(), 'version': guide.data['version'], 'approved_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'scope': 'Local demo partner view only'}
                path = APP / 'private/approvals.json'
                with self.server.lock:
                    rows = json.loads(path.read_text()) if path.exists() else []
                    rows = [a for a in rows if a['id'] != statement['id']] + [statement]
                    path.write_text(json.dumps(rows, indent=2))
                return self.send(201, statement)
            if route == '/api/admin/revoke':
                path = APP / 'private/approvals.json'
                with self.server.lock:
                    rows = json.loads(path.read_text()) if path.exists() else []
                    path.write_text(json.dumps([a for a in rows if a['id'] != body.get('id')], indent=2))
                return self.send(200, {'revoked': True})
            return self.send(404, {'error': 'Route not found'})
        except PermissionError as err:
            return self.send(403, {'error': str(err)})
        except (ValueError, TypeError) as err:
            return self.send(400, {'error': str(err)})

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    server = DemoServer(('127.0.0.1', args.port))
    print('QNu Market Access Guide: http://127.0.0.1:' + str(args.port), flush=True)
    print('LOCAL DEMO ONLY: role switch is not authentication. Internal data; do not expose publicly.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
