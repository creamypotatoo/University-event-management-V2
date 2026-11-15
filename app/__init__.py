from flask import Flask, render_template
from .config import settings
from . import db


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(settings())
    if test_config:
        app.config.update(test_config)
    if app.config['DB_NAME'] != 'university_events_raw':
        raise ValueError('Only university_events_raw is permitted.')
    if not app.config.get('SECRET_KEY') or len(app.config['SECRET_KEY']) < 32:
        raise ValueError('Configure a private SECRET_KEY of at least 32 characters in this project .env.')
    from . import security, auth, management, events, reports, demo_seed
    security.init_app(app)
    auth.init_app(app)
    app.register_blueprint(management.bp)
    app.register_blueprint(events.bp)
    app.register_blueprint(reports.bp)
    from .routes import bp
    app.register_blueprint(bp)
    db.init_app(app)
    demo_seed.init_app(app)

    @app.errorhandler(db.DatabaseUnavailable)
    def unavailable(error):
        from flask import g
        from flask_login import AnonymousUserMixin
        g._login_user = AnonymousUserMixin()
        return render_template('errors/error.html', code=503,
                               message='Database services are temporarily unavailable. Check the connection and try again.'), 503

    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/error.html', code=404, message='Page not found.'), 404

    @app.errorhandler(500)
    def server_error(error):
        return render_template('errors/error.html', code=500, message='An unexpected error occurred.'), 500

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(409)
    @app.errorhandler(413)
    def client_error(error):
        return render_template('errors/error.html', code=error.code, message=error.description), error.code

    @app.errorhandler(db.Conflict)
    def conflict(error):
        return render_template('errors/error.html', code=409, message=str(error)), 409

    return app
