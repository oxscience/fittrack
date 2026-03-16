from database import get_db


def get_setting(key, default=None):
    db = get_db()
    row = db.execute('SELECT value FROM app_settings WHERE key = ?', (key,)).fetchone()
    return row['value'] if row else default


def set_setting(key, value):
    db = get_db()
    db.execute('''
        INSERT INTO app_settings (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
    ''', (key, value))
    db.commit()


def get_settings_dict(*keys):
    db = get_db()
    placeholders = ','.join('?' * len(keys))
    rows = db.execute(
        f'SELECT key, value FROM app_settings WHERE key IN ({placeholders})', keys
    ).fetchall()
    return {r['key']: r['value'] for r in rows}


def is_setup_complete():
    return get_setting('setup_complete') == '1'


def get_email_config():
    keys = [
        'smtp_host', 'smtp_port', 'smtp_user', 'smtp_password', 'smtp_encryption',
        'imap_host', 'imap_port', 'imap_user', 'imap_password', 'imap_encryption',
        'email_from_name', 'email_from_address'
    ]
    config = get_settings_dict(*keys)
    if not config.get('smtp_host'):
        return None
    return config


def get_app_branding():
    return {
        'app_name': get_setting('app_name', 'FitTrack'),
        'app_tagline': get_setting('app_tagline', 'Workout-Tracking, einfach gemacht.'),
        'app_icon': get_setting('app_icon', ''),
        'sender_name': get_setting('email_from_name', '')
    }
