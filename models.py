from database import get_db
from auth import hash_password


# ── Users ──────────────────────────────────────────────

def create_user(email, password, name, role):
    db = get_db()
    db.execute(
        'INSERT INTO user (email, password_hash, name, role) VALUES (?, ?, ?, ?)',
        (email.lower().strip(), hash_password(password), name.strip(), role)
    )
    db.commit()
    return get_user_by_email(email)


def get_user(user_id):
    db = get_db()
    row = db.execute('SELECT * FROM user WHERE id = ?', (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_email(email):
    db = get_db()
    row = db.execute('SELECT * FROM user WHERE email = ?', (email.lower().strip(),)).fetchone()
    return dict(row) if row else None


# ── Trainer-Trainee ────────────────────────────────────

def link_trainer_trainee(trainer_id, trainee_id):
    db = get_db()
    db.execute(
        'INSERT OR IGNORE INTO trainer_trainee (trainer_id, trainee_id) VALUES (?, ?)',
        (trainer_id, trainee_id)
    )
    db.commit()


def get_trainees(trainer_id):
    db = get_db()
    rows = db.execute('''
        SELECT u.id, u.name, u.email, tt.notes, tt.created_at as linked_at
        FROM trainer_trainee tt
        JOIN user u ON u.id = tt.trainee_id
        WHERE tt.trainer_id = ?
        ORDER BY u.name
    ''', (trainer_id,)).fetchall()
    return [dict(r) for r in rows]


def get_trainers(trainee_id):
    db = get_db()
    rows = db.execute('''
        SELECT u.id, u.name, u.email
        FROM trainer_trainee tt
        JOIN user u ON u.id = tt.trainer_id
        WHERE tt.trainee_id = ?
    ''', (trainee_id,)).fetchall()
    return [dict(r) for r in rows]


def update_trainee_notes(trainer_id, trainee_id, notes):
    db = get_db()
    db.execute(
        'UPDATE trainer_trainee SET notes = ? WHERE trainer_id = ? AND trainee_id = ?',
        (notes, trainer_id, trainee_id)
    )
    db.commit()


# ── Invites ────────────────────────────────────────────

def create_invite(trainer_id, code):
    db = get_db()
    db.execute(
        'INSERT INTO invite (trainer_id, code) VALUES (?, ?)',
        (trainer_id, code)
    )
    db.commit()


def get_invite_by_code(code):
    db = get_db()
    row = db.execute('SELECT * FROM invite WHERE code = ? AND used_by IS NULL', (code,)).fetchone()
    return dict(row) if row else None


def use_invite(code, user_id):
    db = get_db()
    db.execute('UPDATE invite SET used_by = ? WHERE code = ?', (user_id, code))
    db.commit()


def get_trainer_invites(trainer_id):
    db = get_db()
    rows = db.execute('''
        SELECT i.*, u.name as used_by_name
        FROM invite i
        LEFT JOIN user u ON u.id = i.used_by
        WHERE i.trainer_id = ?
        ORDER BY i.created_at DESC
    ''', (trainer_id,)).fetchall()
    return [dict(r) for r in rows]


# ── Exercises ──────────────────────────────────────────

def get_exercises(muscle_group=None, equipment=None, search=None, created_by=None):
    db = get_db()
    sql = 'SELECT * FROM exercise WHERE 1=1'
    params = []
    if muscle_group:
        sql += ' AND muscle_group = ?'
        params.append(muscle_group)
    if equipment:
        sql += ' AND equipment = ?'
        params.append(equipment)
    if search:
        sql += ' AND name LIKE ?'
        params.append(f'%{search}%')
    if created_by is not None:
        sql += ' AND (created_by IS NULL OR created_by = ?)'
        params.append(created_by)
    else:
        sql += ' AND created_by IS NULL'
    sql += ' ORDER BY muscle_group, name'
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def get_exercise(exercise_id):
    db = get_db()
    row = db.execute('SELECT * FROM exercise WHERE id = ?', (exercise_id,)).fetchone()
    return dict(row) if row else None


def create_exercise(name, muscle_group, equipment, created_by):
    db = get_db()
    db.execute(
        'INSERT INTO exercise (name, muscle_group, equipment, created_by) VALUES (?, ?, ?, ?)',
        (name.strip(), muscle_group, equipment, created_by)
    )
    db.commit()


# ── Workouts ───────────────────────────────────────────

def create_workout(user_id, routine_id=None):
    db = get_db()
    cursor = db.execute(
        'INSERT INTO workout (user_id, routine_id) VALUES (?, ?)',
        (user_id, routine_id)
    )
    db.commit()
    return get_workout(cursor.lastrowid)


def get_workout(workout_id):
    db = get_db()
    row = db.execute('SELECT * FROM workout WHERE id = ?', (workout_id,)).fetchone()
    if not row:
        return None
    workout = dict(row)
    workout['sets'] = get_workout_sets(workout_id)
    return workout


def get_active_workout(user_id):
    db = get_db()
    row = db.execute(
        'SELECT * FROM workout WHERE user_id = ? AND finished_at IS NULL ORDER BY started_at DESC LIMIT 1',
        (user_id,)
    ).fetchone()
    if not row:
        return None
    workout = dict(row)
    workout['sets'] = get_workout_sets(workout['id'])
    return workout


def finish_workout(workout_id, notes=''):
    db = get_db()
    workout = get_workout(workout_id)
    if not workout:
        return None
    db.execute('''
        UPDATE workout
        SET finished_at = CURRENT_TIMESTAMP,
            duration_seconds = CAST((julianday(CURRENT_TIMESTAMP) - julianday(started_at)) * 86400 AS INTEGER),
            notes = ?
        WHERE id = ?
    ''', (notes, workout_id))
    db.commit()
    return get_workout(workout_id)


def discard_workout(workout_id):
    db = get_db()
    db.execute('DELETE FROM workout WHERE id = ?', (workout_id,))
    db.commit()


def get_workout_history(user_id, limit=50, offset=0):
    db = get_db()
    rows = db.execute('''
        SELECT w.*,
            (SELECT COUNT(DISTINCT exercise_id) FROM workout_set WHERE workout_id = w.id) as exercise_count,
            (SELECT COALESCE(SUM(reps * weight), 0) FROM workout_set WHERE workout_id = w.id) as total_volume
        FROM workout w
        WHERE w.user_id = ? AND w.finished_at IS NOT NULL
        ORDER BY w.started_at DESC
        LIMIT ? OFFSET ?
    ''', (user_id, limit, offset)).fetchall()
    return [dict(r) for r in rows]


# ── Workout Sets ───────────────────────────────────────

def add_workout_set(workout_id, exercise_id, set_number, reps=None, weight=None, rpe=None, set_type='normal'):
    db = get_db()
    cursor = db.execute(
        '''INSERT INTO workout_set (workout_id, exercise_id, set_number, reps, weight, rpe, set_type)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (workout_id, exercise_id, set_number, reps, weight, rpe, set_type)
    )
    db.commit()
    return cursor.lastrowid


def update_workout_set(set_id, reps=None, weight=None, rpe=None, set_type=None):
    db = get_db()
    fields = []
    params = []
    if reps is not None:
        fields.append('reps = ?')
        params.append(reps)
    if weight is not None:
        fields.append('weight = ?')
        params.append(weight)
    if rpe is not None:
        fields.append('rpe = ?')
        params.append(rpe)
    if set_type is not None:
        fields.append('set_type = ?')
        params.append(set_type)
    if not fields:
        return
    params.append(set_id)
    db.execute(f'UPDATE workout_set SET {", ".join(fields)} WHERE id = ?', params)
    db.commit()


def delete_workout_set(set_id):
    db = get_db()
    db.execute('DELETE FROM workout_set WHERE id = ?', (set_id,))
    db.commit()


def get_workout_sets(workout_id):
    db = get_db()
    rows = db.execute('''
        SELECT ws.*, e.name as exercise_name, e.muscle_group, e.equipment
        FROM workout_set ws
        JOIN exercise e ON e.id = ws.exercise_id
        WHERE ws.workout_id = ?
        ORDER BY ws.exercise_id, ws.set_number
    ''', (workout_id,)).fetchall()
    return [dict(r) for r in rows]


def get_workout_exercises(workout_id):
    """Get unique exercises in a workout, grouped."""
    db = get_db()
    rows = db.execute('''
        SELECT DISTINCT e.id, e.name, e.muscle_group, e.equipment
        FROM workout_set ws
        JOIN exercise e ON e.id = ws.exercise_id
        WHERE ws.workout_id = ?
        ORDER BY MIN(ws.id)
    ''', (workout_id,)).fetchall()
    return [dict(r) for r in rows]


def get_last_performance(user_id, exercise_id):
    """Get sets from the user's most recent completed workout for this exercise."""
    db = get_db()
    rows = db.execute('''
        SELECT ws.set_number, ws.reps, ws.weight, ws.rpe, ws.set_type
        FROM workout_set ws
        JOIN workout w ON w.id = ws.workout_id
        WHERE w.user_id = ? AND ws.exercise_id = ? AND w.finished_at IS NOT NULL
        ORDER BY w.started_at DESC, ws.set_number
    ''', (user_id, exercise_id)).fetchall()
    if not rows:
        return []
    # Get only sets from the most recent workout
    first_workout = None
    result = []
    for r in rows:
        r = dict(r)
        if first_workout is None:
            first_workout = True
            result.append(r)
        elif len(result) < 20:
            result.append(r)
        else:
            break
    return result


def get_exercise_progress(user_id, exercise_id, limit=30):
    """Get max weight and total volume per workout for this exercise."""
    db = get_db()
    rows = db.execute('''
        SELECT w.started_at as date,
               MAX(ws.weight) as max_weight,
               SUM(ws.reps * ws.weight) as volume,
               MAX(ws.reps) as max_reps
        FROM workout_set ws
        JOIN workout w ON w.id = ws.workout_id
        WHERE w.user_id = ? AND ws.exercise_id = ? AND w.finished_at IS NOT NULL
        GROUP BY w.id
        ORDER BY w.started_at DESC
        LIMIT ?
    ''', (user_id, exercise_id, limit)).fetchall()
    return [dict(r) for r in reversed(rows)]


# ── Routines ───────────────────────────────────────────

def create_routine(name, created_by):
    db = get_db()
    cursor = db.execute(
        'INSERT INTO routine (name, created_by) VALUES (?, ?)',
        (name.strip(), created_by)
    )
    db.commit()
    return get_routine(cursor.lastrowid)


def get_routine(routine_id):
    db = get_db()
    row = db.execute('SELECT * FROM routine WHERE id = ?', (routine_id,)).fetchone()
    if not row:
        return None
    routine = dict(row)
    routine['exercises'] = get_routine_exercises(routine_id)
    routine['assignees'] = get_routine_assignments(routine_id)
    return routine


def get_routines_for_user(user_id):
    """Get routines created by or assigned to this user."""
    db = get_db()
    rows = db.execute('''
        SELECT DISTINCT r.*, u.name as creator_name
        FROM routine r
        JOIN user u ON u.id = r.created_by
        LEFT JOIN routine_assignment ra ON ra.routine_id = r.id
        WHERE r.created_by = ? OR ra.user_id = ?
        ORDER BY r.name
    ''', (user_id, user_id)).fetchall()
    routines = []
    for r in rows:
        routine = dict(r)
        routine['assignees'] = get_routine_assignments(routine['id'])
        routines.append(routine)
    return routines


def get_routine_exercises(routine_id):
    db = get_db()
    rows = db.execute('''
        SELECT re.*, e.name as exercise_name, e.muscle_group, e.equipment
        FROM routine_exercise re
        JOIN exercise e ON e.id = re.exercise_id
        WHERE re.routine_id = ?
        ORDER BY re.position
    ''', (routine_id,)).fetchall()
    return [dict(r) for r in rows]


def add_routine_exercise(routine_id, exercise_id, position, target_sets=3, target_reps=10, target_weight=None, notes='', superset_group=None):
    db = get_db()
    db.execute(
        '''INSERT INTO routine_exercise (routine_id, exercise_id, position, target_sets, target_reps, target_weight, notes, superset_group)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (routine_id, exercise_id, position, target_sets, target_reps, target_weight, notes, superset_group)
    )
    db.commit()


def delete_routine(routine_id):
    db = get_db()
    db.execute('DELETE FROM routine WHERE id = ?', (routine_id,))
    db.commit()


def clear_routine_exercises(routine_id):
    db = get_db()
    db.execute('DELETE FROM routine_exercise WHERE routine_id = ?', (routine_id,))
    db.commit()


def update_routine(routine_id, name=None):
    db = get_db()
    if name is not None:
        db.execute('UPDATE routine SET name = ? WHERE id = ?', (name.strip(), routine_id))
        db.commit()


def assign_routine(routine_id, user_id):
    db = get_db()
    db.execute(
        'INSERT OR IGNORE INTO routine_assignment (routine_id, user_id) VALUES (?, ?)',
        (routine_id, user_id)
    )
    db.commit()


def unassign_routine(routine_id, user_id):
    db = get_db()
    db.execute(
        'DELETE FROM routine_assignment WHERE routine_id = ? AND user_id = ?',
        (routine_id, user_id)
    )
    db.commit()


def get_routine_assignments(routine_id):
    db = get_db()
    rows = db.execute('''
        SELECT u.id, u.name, u.email
        FROM routine_assignment ra
        JOIN user u ON u.id = ra.user_id
        WHERE ra.routine_id = ?
        ORDER BY u.name
    ''', (routine_id,)).fetchall()
    return [dict(r) for r in rows]


# ── Trainer Stats ──────────────────────────────────────

def get_trainee_stats(trainee_id):
    db = get_db()
    stats = {}

    # Last workout
    row = db.execute('''
        SELECT started_at, duration_seconds FROM workout
        WHERE user_id = ? AND finished_at IS NOT NULL
        ORDER BY started_at DESC LIMIT 1
    ''', (trainee_id,)).fetchone()
    stats['last_workout'] = dict(row) if row else None

    # Workouts in last 7 days
    stats['workouts_7d'] = db.execute('''
        SELECT COUNT(*) FROM workout
        WHERE user_id = ? AND finished_at IS NOT NULL
        AND started_at >= datetime('now', '-7 days')
    ''', (trainee_id,)).fetchone()[0]

    # Workouts in last 30 days
    stats['workouts_30d'] = db.execute('''
        SELECT COUNT(*) FROM workout
        WHERE user_id = ? AND finished_at IS NOT NULL
        AND started_at >= datetime('now', '-30 days')
    ''', (trainee_id,)).fetchone()[0]

    # Current streak (consecutive days with workouts)
    rows = db.execute('''
        SELECT DISTINCT date(started_at) as d FROM workout
        WHERE user_id = ? AND finished_at IS NOT NULL
        ORDER BY d DESC
    ''', (trainee_id,)).fetchall()
    streak = 0
    from datetime import date, timedelta
    today = date.today()
    for i, r in enumerate(rows):
        workout_date = date.fromisoformat(r['d'])
        expected = today - timedelta(days=i)
        if workout_date == expected or (i == 0 and workout_date == today - timedelta(days=1)):
            streak += 1
        else:
            break
    stats['streak'] = streak

    return stats


# ── Sent Emails ───────────────────────────────────────

def get_sent_email_by_message_id(message_id):
    db = get_db()
    row = db.execute('SELECT * FROM sent_email WHERE message_id = ?', (message_id,)).fetchone()
    return dict(row) if row else None


def get_sent_emails_for_trainee(trainee_id, limit=20):
    db = get_db()
    rows = db.execute('''
        SELECT se.*, r.name as routine_name
        FROM sent_email se
        LEFT JOIN routine r ON r.id = se.routine_id
        WHERE se.trainee_id = ?
        ORDER BY se.sent_at DESC LIMIT ?
    ''', (trainee_id, limit)).fetchall()
    return [dict(r) for r in rows]


def get_pending_review_workouts(trainer_id=None):
    db = get_db()
    sql = '''
        SELECT w.*, u.name as trainee_name, u.email as trainee_email
        FROM workout w
        JOIN user u ON u.id = w.user_id
        WHERE w.source = 'email' AND w.review_status = 'pending'
    '''
    params = []
    if trainer_id:
        sql += ' AND w.user_id IN (SELECT trainee_id FROM trainer_trainee WHERE trainer_id = ?)'
        params.append(trainer_id)
    sql += ' ORDER BY w.created_at DESC'
    rows = db.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def update_workout_review(workout_id, status):
    db = get_db()
    db.execute('UPDATE workout SET review_status = ? WHERE id = ?', (status, workout_id))
    db.commit()
