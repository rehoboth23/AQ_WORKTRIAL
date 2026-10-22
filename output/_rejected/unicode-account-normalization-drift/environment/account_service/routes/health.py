"""Health check routes for the account service.

Provides liveness and readiness endpoints for monitoring
and load balancer integration.
"""
from flask import Blueprint, jsonify
from account_service.db import get_connection

health_bp = Blueprint('health', __name__)


@health_bp.route('', methods=['GET'])
def health_check():
    """Basic health check endpoint.

    Returns the service status and database connectivity.

    Response JSON:
        status (str): 'healthy' or 'degraded'
        database (str): 'ok' or 'error'
    """
    db_ok = False
    try:
        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
        db_ok = True
    except Exception:
        pass

    status = 'healthy' if db_ok else 'degraded'
    code = 200 if db_ok else 503

    return jsonify({
        'status': status,
        'database': 'ok' if db_ok else 'error',
    }), code


@health_bp.route('/ready', methods=['GET'])
def readiness_check():
    """Readiness check for load balancers.

    Returns 200 if the service is ready to accept traffic,
    503 otherwise.

    Response JSON:
        ready (bool): Whether the service is ready
    """
    try:
        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
        return jsonify({'ready': True}), 200
    except Exception:
        return jsonify({'ready': False}), 503


@health_bp.route('/info', methods=['GET'])
def service_info():
    """Service information endpoint.

    Returns basic information about the running service.

    Response JSON:
        service (str): Service name
        version (str): Service version
        normalization_form (str): Active normalization form
    """
    from account_service.normalize import get_normalization_form

    return jsonify({
        'service': 'account-service',
        'version': '1.0.0',
        'normalization_form': get_normalization_form(),
    }), 200
