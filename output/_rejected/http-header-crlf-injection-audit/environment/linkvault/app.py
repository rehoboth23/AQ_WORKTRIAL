"""LinkVault URL shortener - main application."""

import string
import random
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from linkvault.store import (
    init_db, get_link, create_link, get_user,
    update_display_name, get_display_name, create_session
)
from linkvault.auth import set_last_user_cookie, check_auth, verify_password
from linkvault.response import JSONResponse


class LinkVaultHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        path = self.path
        if path.startswith('/go/'):
            self._handle_redirect(path[4:])
        elif path.startswith('/api/shorten'):
            self._handle_shorten()
        elif path == '/dashboard':
            self._handle_dashboard()
        else:
            self._send_error(404, 'Not Found')

    def do_POST(self):
        path = self.path
        if path == '/login':
            self._handle_login()
        elif path == '/api/profile':
            self._handle_profile()
        else:
            self._send_error(404, 'Not Found')

    def _handle_redirect(self, code):
        url = get_link(code)
        if url is None:
            self._send_error(404, 'Not Found')
            return
        self.send_response(302)
        self.send_header('Location', url)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def _handle_shorten(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        url = params.get('url', [None])[0]
        request_id = params.get('request_id', [None])[0]

        if not url:
            self._send_error(400, 'Missing url parameter')
            return

        # Validate URL scheme
        parsed_url = urlparse(url)
        if parsed_url.scheme not in ('http', 'https'):
            self._send_error(400, f'Invalid URL: {url}')
            return

        # Generate a short code
        code = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        user = check_auth(self)
        create_link(code, url, created_by=user)

        headers = {}
        if request_id:
            headers['X-Request-Id'] = request_id

        resp = JSONResponse(
            self, status=201, reason='Created',
            body={'code': code, 'url': url},
            headers=headers
        )
        resp.send()

    def _handle_login(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        params = parse_qs(body)
        username = params.get('username', [''])[0]
        password = params.get('password', [''])[0]

        user = get_user(username)
        if user and verify_password(password, user['password_hash']):
            session_id = create_session(username)
            self.send_response(302)
            self.send_header('Set-Cookie', f'session={session_id}; Path=/')
            self.send_header('Location', '/dashboard')
            set_last_user_cookie(self, username)
            self.send_header('Content-Length', '0')
            self.end_headers()
        else:
            self.send_response(401)
            set_last_user_cookie(self, username)
            body_bytes = b'{"error":"invalid credentials"}'
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body_bytes)))
            self.end_headers()
            self.wfile.write(body_bytes)

    def _handle_profile(self):
        user = check_auth(self)
        if user is None:
            self._send_error(401, 'Unauthorized')
            return

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        params = parse_qs(body)
        display_name = params.get('display_name', [None])[0]

        if display_name is not None:
            update_display_name(user, display_name)

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        body_bytes = b'{"ok":true}'
        self.send_header('Content-Length', str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def _handle_dashboard(self):
        user = check_auth(self)
        if user is None:
            self._send_error(401, 'Unauthorized')
            return

        display_name = get_display_name(user) or user
        html = f'<h1>Welcome, {display_name}</h1>'.encode('utf-8')

        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('X-Display-Name', display_name)
        self.send_header('Content-Length', str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def _send_error(self, code, message):
        self.send_response(code, message)
        self.send_header('Content-Type', 'text/plain')
        body_bytes = f'{code} {message}'.encode('utf-8')
        self.send_header('Content-Length', str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def log_message(self, format, *args):
        pass  # Suppress request logging


def main():
    init_db()
    server = HTTPServer(('0.0.0.0', 8080), LinkVaultHandler)
    print('LinkVault running on port 8080', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
