"""WSGI middleware for the account service.

Provides input sanitization middleware that normalizes URL paths
to ensure consistent routing for Unicode characters.
"""
import unicodedata


class InputSanitizationMiddleware:
    """Middleware that normalizes URL paths for consistent routing.

    Ensures that Unicode characters in URL paths are in a consistent form
    for matching and routing. This handles the case where different clients
    may encode the same visual path differently.

    Note: This middleware normalizes PATH_INFO in the WSGI environ
    for consistent URL routing.
    """

    def __init__(self, app):
        """Initialize the middleware with the WSGI application.

        Args:
            app: The WSGI application to wrap.
        """
        self.app = app

    def __call__(self, environ, start_response):
        """Process the request through the middleware.

        Normalizes PATH_INFO to a consistent form before passing the request
        to the wrapped application.

        Args:
            environ: WSGI environment dictionary.
            start_response: WSGI start_response callable.

        Returns:
            The response from the wrapped application.
        """
        path_info = environ.get('PATH_INFO', '')
        if path_info:
            normalized = unicodedata.normalize('NFC', path_info)
            environ['PATH_INFO'] = normalized

        # Also normalize SCRIPT_NAME if present
        script_name = environ.get('SCRIPT_NAME', '')
        if script_name:
            environ['SCRIPT_NAME'] = unicodedata.normalize('NFC', script_name)

        return self.app(environ, start_response)


class RequestLoggingMiddleware:
    """Middleware that logs basic request information.

    Logs the HTTP method, path, and response status for each request.
    Useful for debugging and monitoring.
    """

    def __init__(self, app, logger=None):
        """Initialize with the WSGI application and optional logger.

        Args:
            app: The WSGI application to wrap.
            logger: Optional logging.Logger instance. If None, a
                   basic logger is created.
        """
        self.app = app
        self.logger = logger

    def __call__(self, environ, start_response):
        """Process and log the request."""
        method = environ.get('REQUEST_METHOD', 'UNKNOWN')
        path = environ.get('PATH_INFO', '/')

        def logging_start_response(status, headers, exc_info=None):
            if self.logger:
                self.logger.info(f"{method} {path} -> {status}")
            return start_response(status, headers, exc_info)

        return self.app(environ, logging_start_response)
