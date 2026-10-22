import json
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

from docvault import db
from docvault.helpers import (
    make_content_disposition,
    RedirectMixin,
    set_starred_cookie,
    format_json_response,
)
from docvault.config import HOST, PORT


class DocVaultHandler(BaseHTTPRequestHandler, RedirectMixin):

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == '/api/docs':
            docs = db.list_docs()
            format_json_response(self, docs)

        elif path.startswith('/api/docs/'):
            title = urllib.parse.unquote(path[len('/api/docs/'):])
            doc = db.get_doc(title)
            if doc:
                format_json_response(self, doc)
            else:
                format_json_response(self, {'error': 'not found'}, 404)

        elif path.startswith('/api/exports/'):
            filename = urllib.parse.unquote(path[len('/api/exports/'):])
            disposition = make_content_disposition(filename)
            self.send_response(200)
            self.send_header('Content-Disposition', disposition)
            self.send_header('Content-Type', 'application/octet-stream')
            self.end_headers()
            self.wfile.write(b'export-data')

        elif path == '/login':
            next_url = query.get('next', ['/'])[0]
            self.send_response(302)
            self.send_header('Location', next_url)
            self.end_headers()

        elif path.startswith('/api/go/'):
            code = urllib.parse.unquote(path[len('/api/go/'):])
            url = db.get_shortcut(code)
            if url:
                self.do_redirect(url)
            else:
                format_json_response(self, {'error': 'shortcut not found'}, 404)

        else:
            format_json_response(self, {'error': 'not found'}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else ''

        if path == '/api/docs':
            try:
                data = json.loads(body)
                title = data.get('title', 'Untitled')
                author = data.get('author', 'Unknown')
                content = data.get('content', '')
                db.create_doc(title, author, content)
                self.send_response(201)
                self.send_header('X-Authored-By', author)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'title': title, 'author': author}).encode('utf-8'))
            except (json.JSONDecodeError, KeyError):
                format_json_response(self, {'error': 'bad request'}, 400)

        elif path.startswith('/api/docs/') and path.endswith('/star'):
            title = urllib.parse.unquote(path[len('/api/docs/'):-len('/star')])
            self.send_response(200)
            set_starred_cookie(self, title)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'starred': title}).encode('utf-8'))

        elif path == '/api/prefs':
            try:
                data = json.loads(body)
                layout = data.get('layout', 'default')
                db.set_pref('layout', layout)
                self.send_response(200)
                self.send_header('Set-Cookie', f'layout={layout}; Path=/')
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'layout': layout}).encode('utf-8'))
            except (json.JSONDecodeError, KeyError):
                format_json_response(self, {'error': 'bad request'}, 400)

        elif path == '/api/shortcuts':
            try:
                data = json.loads(body)
                code = data.get('code', '')
                url = data.get('url', '')
                db.create_shortcut(code, url)
                format_json_response(self, {'code': code, 'url': url}, 201)
            except (json.JSONDecodeError, KeyError):
                format_json_response(self, {'error': 'bad request'}, 400)

        else:
            format_json_response(self, {'error': 'not found'}, 404)


def main():
    db.init_db()
    server = HTTPServer((HOST, PORT), DocVaultHandler)
    print(f'DocVault running on {HOST}:{PORT}')
    server.serve_forever()


if __name__ == '__main__':
    main()
