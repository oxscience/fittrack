import smtplib
import imaplib
import email as email_lib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr, formatdate, make_msgid
from email.header import decode_header
from database import get_db
from settings import get_email_config, get_app_branding


# ── SMTP Sending ──────────────────────────────────────

def send_training_plan(routine, trainee, routine_exercises):
    """Send a training plan email to a trainee. Returns message_id or None."""
    config = get_email_config()
    if not config:
        return None

    branding = get_app_branding()
    subject = f"Dein Trainingsplan: {routine['name']}"
    body = _build_plan_text(routine, routine_exercises, branding)

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = formataddr((
        config.get('email_from_name', branding['app_name']),
        config['email_from_address']
    ))
    msg['To'] = trainee['email']
    msg['Date'] = formatdate(localtime=True)

    domain = config['email_from_address'].split('@')[1] if '@' in config['email_from_address'] else 'fittrack.local'
    message_id = make_msgid(domain=domain)
    msg['Message-ID'] = message_id

    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    if not _smtp_send(config, trainee['email'], msg):
        return None

    # Store in DB
    db = get_db()
    db.execute(
        'INSERT INTO sent_email (routine_id, trainee_id, message_id, subject) VALUES (?, ?, ?, ?)',
        (routine['id'], trainee['id'], message_id, subject)
    )
    db.commit()
    return message_id


def send_reminder(trainee, original_message_id, reminder_type='evening'):
    """Send a reminder email referencing the original training plan."""
    config = get_email_config()
    if not config:
        return None

    branding = get_app_branding()

    if reminder_type == 'evening':
        subject = "Hast du heute trainiert?"
        body = (
            "Hi! Hast du dein Training heute geschafft?\n\n"
            "Antworte einfach auf diese E-Mail mit deinen Ergebnissen.\n\n"
            "Beispiel:\n"
            "  80/80/85 je 8\n"
            "  3x10 @ 60kg\n"
            "  wie geplant"
        )
    else:
        subject = "Training-Erinnerung"
        body = "Vergiss nicht dein Training heute!"

    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = formataddr((
        config.get('email_from_name', branding['app_name']),
        config['email_from_address']
    ))
    msg['To'] = trainee['email']
    msg['Date'] = formatdate(localtime=True)
    msg['In-Reply-To'] = original_message_id
    msg['References'] = original_message_id

    domain = config['email_from_address'].split('@')[1] if '@' in config['email_from_address'] else 'fittrack.local'
    message_id = make_msgid(domain=domain)
    msg['Message-ID'] = message_id

    if not _smtp_send(config, trainee['email'], msg):
        return None

    db = get_db()
    db.execute(
        'INSERT INTO sent_email (routine_id, trainee_id, message_id, subject, reminder_type) VALUES (?, ?, ?, ?, ?)',
        (None, trainee['id'], message_id, subject, reminder_type)
    )
    db.commit()
    return message_id


def _smtp_send(config, to_email, msg):
    """Send an email via SMTP. Returns True on success."""
    try:
        encryption = config.get('smtp_encryption', 'starttls')
        if encryption == 'ssl':
            server = smtplib.SMTP_SSL(config['smtp_host'], int(config.get('smtp_port', 465)), timeout=15)
        else:
            server = smtplib.SMTP(config['smtp_host'], int(config.get('smtp_port', 587)), timeout=15)
            if encryption == 'starttls':
                server.starttls()
        server.login(config['smtp_user'], config['smtp_password'])
        server.sendmail(config['email_from_address'], [to_email], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"SMTP error: {e}")
        return False


def _build_plan_text(routine, exercises, branding):
    lines = [
        f"Trainingsplan: {routine['name']}",
        f"von {branding['app_name']}",
        "",
        "━" * 36,
    ]
    for i, ex in enumerate(exercises, 1):
        name = ex.get('exercise_name') or ex.get('name', '?')
        weight_str = f" @ {ex['target_weight']}kg" if ex.get('target_weight') else ""
        lines.append(f"{i}. {name}")
        lines.append(f"   {ex.get('target_sets', 3)} Sätze x {ex.get('target_reps', 10)} Wdh{weight_str}")
        if ex.get('notes'):
            lines.append(f"   Hinweis: {ex['notes']}")
        lines.append("")

    lines.extend([
        "━" * 36,
        "",
        "Antworte einfach mit deinen Ergebnissen!",
        "",
        "Beispiele:",
        '  "80/80/85 je 8" = 3 Sätze: 80x8, 80x8, 85x8',
        '  "3x8 @ 80kg" = 3 Sätze: 80x8',
        '  "wie geplant" = Zielwerte übernommen',
        '  "übersprungen" = als übersprungen markiert',
    ])
    return "\n".join(lines)


# ── IMAP Receiving ────────────────────────────────────

def poll_inbox(app):
    """Poll IMAP inbox for replies. Called by scheduler outside request context."""
    with app.app_context():
        config = get_email_config()
        if not config or not config.get('imap_host'):
            return

        try:
            encryption = config.get('imap_encryption', 'ssl')
            if encryption == 'ssl':
                mail = imaplib.IMAP4_SSL(config['imap_host'], int(config.get('imap_port', 993)))
            else:
                mail = imaplib.IMAP4(config['imap_host'], int(config.get('imap_port', 143)))
                if encryption == 'starttls':
                    mail.starttls()

            mail.login(config['imap_user'], config['imap_password'])
            mail.select('INBOX')

            status, data = mail.search(None, 'UNSEEN')
            if status != 'OK':
                mail.logout()
                return

            email_ids = data[0].split()

            for eid in email_ids:
                status, msg_data = mail.fetch(eid, '(RFC822)')
                if status != 'OK':
                    continue

                raw_email = msg_data[0][1]
                msg = email_lib.message_from_bytes(raw_email)

                in_reply_to = msg.get('In-Reply-To', '').strip()
                references = msg.get('References', '').strip()

                # Match against sent emails
                matched_sent = None
                if in_reply_to:
                    matched_sent = _find_sent_email(in_reply_to)
                if not matched_sent and references:
                    for ref in references.split():
                        matched_sent = _find_sent_email(ref.strip())
                        if matched_sent:
                            break

                if not matched_sent:
                    continue

                body = _extract_body(msg)
                if not body:
                    continue

                # Strip quoted text
                try:
                    from email_reply_parser import EmailReplyParser
                    reply = EmailReplyParser.parse_reply(body)
                except Exception:
                    reply = body

                if not reply.strip():
                    continue

                _process_reply(matched_sent, reply.strip())

            mail.logout()

        except Exception as e:
            print(f"IMAP poll error: {e}")


def _find_sent_email(message_id):
    db = get_db()
    row = db.execute('SELECT * FROM sent_email WHERE message_id = ?', (message_id,)).fetchone()
    return dict(row) if row else None


def _extract_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                charset = part.get_content_charset() or 'utf-8'
                return part.get_payload(decode=True).decode(charset, errors='replace')
    else:
        charset = msg.get_content_charset() or 'utf-8'
        return msg.get_payload(decode=True).decode(charset, errors='replace')
    return None


def _process_reply(sent_email, reply_text):
    """Process a parsed reply: create workout + sets in DB."""
    from workout_parser import parse_workout_reply
    from models import get_routine, add_workout_set

    routine = get_routine(sent_email['routine_id']) if sent_email.get('routine_id') else None
    routine_exercises = routine.get('exercises', []) if routine else []

    result = parse_workout_reply(reply_text, routine_exercises)

    if not result.exercises:
        return

    review_status = 'pending' if result.overall_confidence != 'high' else None

    # Create workout
    db = get_db()
    cursor = db.execute(
        '''INSERT INTO workout (user_id, routine_id, source, parse_confidence, review_status,
           started_at, finished_at) VALUES (?, ?, 'email', ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)''',
        (sent_email['trainee_id'], sent_email.get('routine_id'), result.overall_confidence, review_status)
    )
    workout_id = cursor.lastrowid
    db.commit()

    for pe in result.exercises:
        if pe.skipped:
            continue
        for i, (weight, reps) in enumerate(pe.sets, 1):
            add_workout_set(workout_id, pe.exercise_id, i, reps=reps, weight=weight)


# ── Auto Reminders ────────────────────────────────────

def send_morning_plans(app):
    """Send training plans for routines assigned to trainees (not yet sent today)."""
    with app.app_context():
        from settings import get_setting
        if get_setting('reminders_enabled') != '1':
            return

        from models import get_routine

        db = get_db()
        rows = db.execute('''
            SELECT r.id as routine_id, ra.user_id as trainee_id,
                   u.email as trainee_email, u.name as trainee_name
            FROM routine r
            JOIN routine_assignment ra ON ra.routine_id = r.id
            JOIN user u ON u.id = ra.user_id
            WHERE NOT EXISTS (
                SELECT 1 FROM sent_email se
                WHERE se.routine_id = r.id AND se.trainee_id = ra.user_id
                AND date(se.sent_at) = date('now')
            )
        ''').fetchall()

        for row in rows:
            routine = get_routine(row['routine_id'])
            if not routine:
                continue
            trainee = {'id': row['trainee_id'], 'email': row['trainee_email'], 'name': row['trainee_name']}
            send_training_plan(routine, trainee, routine.get('exercises', []))


def send_evening_nudges(app):
    """Send evening nudges for plans sent today with no reply."""
    with app.app_context():
        from settings import get_setting
        if get_setting('reminders_enabled') != '1':
            return

        db = get_db()
        unreplied = db.execute('''
            SELECT se.*, u.email as trainee_email, u.name as trainee_name
            FROM sent_email se
            JOIN user u ON u.id = se.trainee_id
            WHERE date(se.sent_at) = date('now')
            AND se.routine_id IS NOT NULL
            AND se.reminder_type IS NULL
            AND se.trainee_id NOT IN (
                SELECT user_id FROM workout
                WHERE source = 'email' AND date(created_at) = date('now')
            )
            AND se.message_id NOT IN (
                SELECT se2.message_id FROM sent_email se2
                WHERE se2.reminder_type = 'evening' AND date(se2.sent_at) = date('now')
            )
        ''').fetchall()

        for row in unreplied:
            trainee = {'id': row['trainee_id'], 'email': row['trainee_email'], 'name': row['trainee_name']}
            send_reminder(trainee, row['message_id'], reminder_type='evening')
