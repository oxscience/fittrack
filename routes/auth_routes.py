import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from auth import verify_password, get_current_user, login_required
from models import (
    create_user, get_user_by_email, create_invite, get_invite_by_code,
    use_invite, link_trainer_trainee, get_trainer_invites
)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user = get_user_by_email(email)
        if user and verify_password(password, user['password_hash']):
            session['user_id'] = user['id']
            flash(f'Willkommen, {user["name"]}!', 'success')
            if user['role'] == 'trainer':
                return redirect(url_for('trainer.dashboard'))
            return redirect(url_for('workout.dashboard'))
        flash('E-Mail oder Passwort falsch.', 'danger')
    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    invite_code = request.args.get('invite', '')
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        name = request.form.get('name', '').strip()
        role = request.form.get('role', 'trainee')
        invite_code = request.form.get('invite_code', '').strip()

        if not email or not password or not name:
            flash('Alle Felder sind erforderlich.', 'danger')
            return render_template('register.html', invite_code=invite_code)

        if len(password) < 6:
            flash('Passwort muss mindestens 6 Zeichen lang sein.', 'danger')
            return render_template('register.html', invite_code=invite_code)

        if get_user_by_email(email):
            flash('E-Mail-Adresse bereits registriert.', 'danger')
            return render_template('register.html', invite_code=invite_code)

        # If invite code provided, force trainee role
        invite = None
        if invite_code:
            invite = get_invite_by_code(invite_code)
            if not invite:
                flash('Ungültiger oder bereits verwendeter Einladungscode.', 'danger')
                return render_template('register.html', invite_code=invite_code)
            role = 'trainee'

        user = create_user(email, password, name, role)
        if invite:
            use_invite(invite_code, user['id'])
            link_trainer_trainee(invite['trainer_id'], user['id'])

        session['user_id'] = user['id']
        flash(f'Willkommen bei FitTrack, {user["name"]}!', 'success')
        if role == 'trainer':
            return redirect(url_for('trainer.dashboard'))
        return redirect(url_for('workout.dashboard'))

    return render_template('register.html', invite_code=invite_code)


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Abgemeldet.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/invite/create', methods=['POST'])
@login_required
def create_invite_code():
    user = get_current_user()
    if user['role'] != 'trainer':
        flash('Nur Trainer können Einladungen erstellen.', 'danger')
        return redirect(url_for('workout.dashboard'))
    code = uuid.uuid4().hex[:8].upper()
    create_invite(user['id'], code)
    flash(f'Einladungscode erstellt: {code}', 'success')
    return redirect(url_for('trainer.dashboard'))
