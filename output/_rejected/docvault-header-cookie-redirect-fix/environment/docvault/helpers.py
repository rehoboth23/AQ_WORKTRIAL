import json
import uuid


def make_content_disposition(filename):
    return f'attachment; filename="{filename}"'


class RedirectMixin:
    def do_redirect(self, url):
        self.send_response(302)
        self.send_header('Location', url)
        self.end_headers()


def set_starred_cookie(handler, title):
    handler.send_header('Set-Cookie', f'starred={title}; Path=/')


def format_json_response(handler, data, status=200):
    body = json.dumps(data).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Content-Length', str(len(body)))
    handler.send_header('X-Request-Id', str(uuid.uuid4()))
    handler.end_headers()
    handler.wfile.write(body)
