import smtplib
import imaplib
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import get_db
from settings import set_setting, is_setup_complete, get_setting, get_email_config, get_app_branding
from auth import login_required, role_required

setup_bp = Blueprint('setup', __name__)


@setup_bp.route('/setup')
def index():
    if is_setup_complete():
        return redirect(url_for('auth.login'))
    step = int(request.args.get('step', '1'))
    # Step 4 needs summary data
    summary = None
    if step == 4:
        from auth import get_current_user
        user = get_current_user()
        summary = {
            'user': user,
            'email_config': get_email_config(),
            'branding': get_app_branding()
        }
    return render_template('setup.html', step=step, summary=summary)


@setup_bp.route('/setup/step1', methods=['POST'])
def step1():
    if is_setup_complete():
        return redirect(url_for('auth.login'))
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')

    if not name or not email or len(password) < 6:
        flash('Alle Felder ausfüllen (Passwort min. 6 Zeichen).', 'danger')
        return redirect(url_for('setup.index', step=1))

    from models import get_user_by_email, create_user
    if get_user_by_email(email):
        flash('E-Mail bereits registriert.', 'danger')
        return redirect(url_for('setup.index', step=1))

    user = create_user(email, password, name, 'trainer')
    session['user_id'] = user['id']
    return redirect(url_for('setup.index', step=2))


@setup_bp.route('/setup/step2', methods=['POST'])
def step2():
    if is_setup_complete():
        return redirect(url_for('auth.login'))
    for key in [
        'smtp_host', 'smtp_port', 'smtp_user', 'smtp_password', 'smtp_encryption',
        'imap_host', 'imap_port', 'imap_user', 'imap_password', 'imap_encryption',
        'email_from_name', 'email_from_address'
    ]:
        val = request.form.get(key, '').strip()
        if val:
            set_setting(key, val)
    return redirect(url_for('setup.index', step=3))


@setup_bp.route('/setup/step3', methods=['POST'])
def step3():
    if is_setup_complete():
        return redirect(url_for('auth.login'))
    app_name = request.form.get('app_name', 'FitTrack').strip()
    app_tagline = request.form.get('app_tagline', '').strip()
    set_setting('app_name', app_name or 'FitTrack')
    if app_tagline:
        set_setting('app_tagline', app_tagline)
    return redirect(url_for('setup.index', step=4))


@setup_bp.route('/setup/complete', methods=['POST'])
def complete():
    if is_setup_complete():
        return redirect(url_for('auth.login'))
    set_setting('setup_complete', '1')
    flash('Setup abgeschlossen! Willkommen.', 'success')
    return redirect(url_for('trainer.dashboard'))


@setup_bp.route('/setup/test-email', methods=['POST'])
def test_email():
    smtp_host = request.form.get('smtp_host', '')
    smtp_port = int(request.form.get('smtp_port', 587))
    smtp_user = request.form.get('smtp_user', '')
    smtp_password = request.form.get('smtp_password', '')
    smtp_encryption = request.form.get('smtp_encryption', 'starttls')

    imap_host = request.form.get('imap_host', '')
    imap_port = int(request.form.get('imap_port', 993))
    imap_user = request.form.get('imap_user', '')
    imap_password = request.form.get('imap_password', '')
    imap_encryption = request.form.get('imap_encryption', 'ssl')

    results = []

    # Test SMTP
    try:
        if smtp_encryption == 'ssl':
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            if smtp_encryption == 'starttls':
                server.starttls()
        server.login(smtp_user, smtp_password)
        server.quit()
        results.append(('SMTP', True, 'Verbindung erfolgreich'))
    except Exception as e:
        results.append(('SMTP', False, str(e)))

    # Test IMAP
    try:
        if imap_encryption == 'ssl':
            mail = imaplib.IMAP4_SSL(imap_host, imap_port)
        else:
            mail = imaplib.IMAP4(imap_host, imap_port)
            if imap_encryption == 'starttls':
                mail.starttls()
        mail.login(imap_user, imap_password)
        mail.logout()
        results.append(('IMAP', True, 'Verbindung erfolgreich'))
    except Exception as e:
        results.append(('IMAP', False, str(e)))

    return render_template('partials/email_test_result.html', results=results)


# ── Post-setup email settings ──

@setup_bp.route('/settings/email', methods=['GET', 'POST'])
@login_required
@role_required('trainer')
def email_settings():
    if request.method == 'POST':
        for key in [
            'smtp_host', 'smtp_port', 'smtp_user', 'smtp_password', 'smtp_encryption',
            'imap_host', 'imap_port', 'imap_user', 'imap_password', 'imap_encryption',
            'email_from_name', 'email_from_address', 'reminders_enabled'
        ]:
            val = request.form.get(key, '').strip()
            set_setting(key, val)
        flash('E-Mail-Einstellungen gespeichert.', 'success')
        return redirect(url_for('setup.email_settings'))

    config = get_email_config() or {}
    reminders_enabled = get_setting('reminders_enabled', '0')
    return render_template('email_settings.html', config=config, reminders_enabled=reminders_enabled)


@setup_bp.route('/api/app-icon', methods=['POST'])
@login_required
@role_required('trainer')
def update_app_icon():
    icon = request.form.get('icon', '').strip()
    set_setting('app_icon', icon)
    return '', 204
