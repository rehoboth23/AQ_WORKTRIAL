"""Authentication helpers for LinkVault."""

import hashlib


def hash_password(password):
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password, pw_hash):
    """Verify a password against its hash."""
    return hash_password(password) == pw_hash


def set_last_user_cookie(handler, username):
    """Set a last_user cookie so the login form can show the last attempted username."""
    cookie_line = f"Set-Cookie: last_user={username}; Path=/\r\n"
    handler._headers_buffer.append(cookie_line.encode())


def check_auth(handler):
    """Read the session cookie and return the authenticated username, or None."""
    cookie_header = handler.headers.get('Cookie', '')
    if not cookie_header:
        return None
    for part in cookie_header.split(';'):
        part = part.strip()
        if part.startswith('session='):
            session_id = part[len('session='):]
            from linkvault.store import get_session_user
            return get_session_user(session_id)
    return None
