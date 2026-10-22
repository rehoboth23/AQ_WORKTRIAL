"""Flask application factory for the account service.

The application is created via the create_app() factory function,
which loads configuration in the following order:

1. Default values from config.py
2. Runtime overrides from the app_config database table
3. Optional config_overrides dict parameter

The database config override mechanism allows changing settings
without redeploying the application code.
"""
import os
import sys
import logging
from flask import Flask
from account_service.config import DB_PATH, SECRET_KEY, NORMALIZATION_FORM as CONFIG_NORMALIZATION_FORM
from account_service.middleware import InputSanitizationMiddleware
from account_service.error_handlers import register_error_handlers
from account_service.db import get_config_value


logger = logging.getLogger(__name__)


def create_app(config_overrides=None):
    """Create and configure the Flask application.

    Configuration is loaded in this order:
    1. Default config from config.py
    2. Runtime config from app_config database table (overrides config.py)
    3. Optional config_overrides dict (overrides everything)

    The database configuration allows dynamic changes without redeploying.
    When the app starts, it reads the app_config table and applies those
    values on top of the defaults.

    Args:
        config_overrides: Optional dict of configuration overrides.

    Returns:
        A configured Flask application instance.
    """
    app = Flask(__name__)

    # Step 1: Apply defaults from config.py
    app.config['SECRET_KEY'] = SECRET_KEY
    app.config['DB_PATH'] = DB_PATH
    app.config['NORMALIZATION_FORM'] = CONFIG_NORMALIZATION_FORM
    app.config['MAX_USERNAME_LENGTH'] = int(os.environ.get('MAX_USERNAME_LENGTH', '64'))
    app.config['MIN_BALANCE'] = float(os.environ.get('MIN_BALANCE', '-1000.0'))
    app.config['MAX_BALANCE'] = float(os.environ.get('MAX_BALANCE', '999999999.0'))

    # Step 2: Load runtime configuration from the database
    # These values take precedence over config.py defaults
    _load_db_config(app)

    # Step 3: Apply any programmatic overrides
    if config_overrides:
        app.config.update(config_overrides)

    # Sync the module-level config so normalize_for_storage picks it up
    import account_service.config as cfg
    cfg.NORMALIZATION_FORM = app.config['NORMALIZATION_FORM']

    # Set up logging
    if app.config.get('DEBUG'):
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    logger.info(f"Account service starting with NORMALIZATION_FORM={app.config['NORMALIZATION_FORM']}")

    # Register middleware
    app.wsgi_app = InputSanitizationMiddleware(app.wsgi_app)

    # Register error handlers
    register_error_handlers(app)

    # Register route blueprints
    from account_service.routes.auth import auth_bp
    from account_service.routes.accounts import accounts_bp
    from account_service.routes.admin import admin_bp
    from account_service.routes.reports import reports_bp
    from account_service.routes.health import health_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(accounts_bp, url_prefix='/api/accounts')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(reports_bp, url_prefix='/api/reports')
    app.register_blueprint(health_bp, url_prefix='/api/health')

    return app


def _load_db_config(app):
    """Load configuration values from the app_config database table.

    These values override the defaults from config.py. If the database
    is not yet available (e.g., during initial setup), the defaults
    from config.py are used.

    Args:
        app: The Flask application to configure.
    """
    try:
        norm_form = get_config_value('normalization_form')
        if norm_form:
            app.config['NORMALIZATION_FORM'] = norm_form

        max_username = get_config_value('max_username_length')
        if max_username:
            try:
                app.config['MAX_USERNAME_LENGTH'] = int(max_username)
            except (ValueError, TypeError):
                pass

        min_balance = get_config_value('min_balance')
        if min_balance:
            try:
                app.config['MIN_BALANCE'] = float(min_balance)
            except (ValueError, TypeError):
                pass

        max_balance = get_config_value('max_balance')
        if max_balance:
            try:
                app.config['MAX_BALANCE'] = float(max_balance)
            except (ValueError, TypeError):
                pass

    except Exception:
        # If DB isn't available yet (e.g., during initial setup),
        # just use the defaults from config.py
        logger.warning("Could not load database config, using defaults")
        pass
