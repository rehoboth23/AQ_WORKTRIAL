import os

DB_PATH = os.environ.get('DOCVAULT_DB', 'docvault.db')
HOST = os.environ.get('DOCVAULT_HOST', '0.0.0.0')
PORT = int(os.environ.get('DOCVAULT_PORT', '8080'))
