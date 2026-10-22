"""JSON response builder for LinkVault."""

import json


class JSONResponse:
    """Build and send a complete HTTP JSON response.

    Constructs the full response (status line, headers, body) and writes it
    directly to the handler's wfile.
    """

    def __init__(self, handler, status=200, reason='OK', body=None, headers=None):
        self.handler = handler
        self.status = status
        self.reason = reason
        self.body = body or {}
        self.headers = headers or {}

    def send(self):
        body_bytes = json.dumps(self.body).encode('utf-8')
        self.headers['Content-Type'] = 'application/json'
        self.headers['Content-Length'] = str(len(body_bytes))

        # Build the raw HTTP response
        lines = [f'HTTP/1.1 {self.status} {self.reason}\r\n']
        for name, value in self.headers.items():
            lines.append(f'{name}: {value}\r\n')
        lines.append('\r\n')

        response_bytes = ''.join(lines).encode('latin-1') + body_bytes
        self.handler.wfile.write(response_bytes)
        self.handler.wfile.flush()
