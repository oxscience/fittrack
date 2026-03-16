from flask import Flask, request, redirect, url_for
from flask_apscheduler import APScheduler
from database import close_db, init_db
from auth import get_current_user
from routes import register_blueprints
from settings import is_setup_complete, get_app_branding
import config

scheduler = APScheduler()


def create_app():
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY

    app.teardown_appcontext(close_db)

    @app.context_processor
    def inject_globals():
        branding = get_app_branding()
        return dict(current_user=get_current_user(), app_branding=branding)

    @app.before_request
    def check_setup():
        if request.endpoint and (
            request.endpoint.startswith('setup.') or
            request.endpoint == 'static'
        ):
            return
        if not is_setup_complete():
            return redirect(url_for('setup.index'))

    register_blueprints(app)

    with app.app_context():
        init_db()

    # Initialize scheduler
    app.config['SCHEDULER_API_ENABLED'] = False
    scheduler.init_app(app)

    @scheduler.task('interval', id='poll_inbox', minutes=5, misfire_grace_time=60)
    def scheduled_poll():
        from email_service import poll_inbox
        poll_inbox(app)

    @scheduler.task('cron', id='morning_reminders', hour=7, minute=0, misfire_grace_time=300)
    def morning_reminders():
        from email_service import send_morning_plans
        send_morning_plans(app)

    @scheduler.task('cron', id='evening_reminders', hour=20, minute=0, misfire_grace_time=300)
    def evening_reminders():
        from email_service import send_evening_nudges
        send_evening_nudges(app)

    scheduler.start()

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host=config.HOST, port=config.PORT, debug=True)
