from functools import wraps
from flask import session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db


def hash_password(password):
    return generate_password_hash(password)


def verify_password(password, password_hash):
    return check_password_hash(password_hash, password)


def get_current_user():
    user_id = session.get('user_id')
    if user_id is None:
        return None
    db = get_db()
    row = db.execute('SELECT id, email, name, role FROM user WHERE id = ?', (user_id,)).fetchone()
    return dict(row) if row else None


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Bitte zuerst einloggen.', 'warning')
            return redirect(url_for('auth.login'))
        user = get_current_user()
        if not user:
            session.clear()
            flash('Bitte zuerst einloggen.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = get_current_user()
            if not user or user['role'] != role:
                flash('Keine Berechtigung.', 'danger')
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return decorated
    return decorator
