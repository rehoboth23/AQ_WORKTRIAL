"""Error handlers for the Flask application.

Registers standard HTTP error handlers that return JSON responses
instead of HTML error pages. This ensures that API clients always
receive parseable error responses.
"""
from flask import jsonify


def register_error_handlers(app):
    """Register error handlers with the Flask app.

    Installs handlers for common HTTP error codes that return
    structured JSON error responses.

    Args:
        app: The Flask application instance.
    """

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({'error': 'Bad request', 'message': str(e)}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({'error': 'Unauthorized', 'message': str(e)}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({'error': 'Forbidden', 'message': str(e)}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Not found', 'message': str(e)}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({'error': 'Method not allowed', 'message': str(e)}), 405

    @app.errorhandler(409)
    def conflict(e):
        return jsonify({'error': 'Conflict', 'message': str(e)}), 409

    @app.errorhandler(415)
    def unsupported_media_type(e):
        return jsonify({'error': 'Unsupported media type', 'message': str(e)}), 415

    @app.errorhandler(422)
    def unprocessable_entity(e):
        return jsonify({'error': 'Unprocessable entity', 'message': str(e)}), 422

    @app.errorhandler(429)
    def too_many_requests(e):
        return jsonify({'error': 'Too many requests', 'message': str(e)}), 429

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({'error': 'Internal server error', 'message': str(e)}), 500

    @app.errorhandler(503)
    def service_unavailable(e):
        return jsonify({'error': 'Service unavailable', 'message': str(e)}), 503
