import sqlite3
from flask import g
import config


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(config.DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    from seed_exercises import EXERCISES

    db = get_db()
    db.executescript('''
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('trainer', 'trainee')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS trainer_trainee (
            trainer_id INTEGER NOT NULL REFERENCES user(id) ON DELETE CASCADE,
            trainee_id INTEGER NOT NULL REFERENCES user(id) ON DELETE CASCADE,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (trainer_id, trainee_id)
        );

        CREATE TABLE IF NOT EXISTS invite (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trainer_id INTEGER NOT NULL REFERENCES user(id) ON DELETE CASCADE,
            code TEXT UNIQUE NOT NULL,
            used_by INTEGER REFERENCES user(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS exercise (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            muscle_group TEXT NOT NULL,
            equipment TEXT DEFAULT 'bodyweight',
            created_by INTEGER REFERENCES user(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS workout (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES user(id) ON DELETE CASCADE,
            started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMP,
            duration_seconds INTEGER,
            notes TEXT DEFAULT '',
            routine_id INTEGER REFERENCES routine(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS workout_set (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workout_id INTEGER NOT NULL REFERENCES workout(id) ON DELETE CASCADE,
            exercise_id INTEGER NOT NULL REFERENCES exercise(id),
            set_number INTEGER NOT NULL,
            set_type TEXT DEFAULT 'normal' CHECK(set_type IN ('normal', 'warmup', 'dropset', 'failure')),
            reps INTEGER,
            weight REAL,
            rpe REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS routine (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_by INTEGER NOT NULL REFERENCES user(id) ON DELETE CASCADE,
            assigned_to INTEGER REFERENCES user(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS routine_exercise (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            routine_id INTEGER NOT NULL REFERENCES routine(id) ON DELETE CASCADE,
            exercise_id INTEGER NOT NULL REFERENCES exercise(id),
            position INTEGER NOT NULL,
            target_sets INTEGER DEFAULT 3,
            target_reps INTEGER DEFAULT 10,
            target_weight REAL,
            notes TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sent_email (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            routine_id INTEGER REFERENCES routine(id) ON DELETE SET NULL,
            trainee_id INTEGER NOT NULL REFERENCES user(id) ON DELETE CASCADE,
            message_id TEXT UNIQUE NOT NULL,
            subject TEXT NOT NULL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reminder_type TEXT DEFAULT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_workout_user ON workout(user_id);
        CREATE INDEX IF NOT EXISTS idx_workout_started ON workout(started_at);
        CREATE INDEX IF NOT EXISTS idx_workout_set_workout ON workout_set(workout_id);
        CREATE INDEX IF NOT EXISTS idx_exercise_muscle ON exercise(muscle_group);
        CREATE INDEX IF NOT EXISTS idx_routine_created_by ON routine(created_by);
        CREATE INDEX IF NOT EXISTS idx_routine_assigned_to ON routine(assigned_to);
        CREATE TABLE IF NOT EXISTS routine_assignment (
            routine_id INTEGER NOT NULL REFERENCES routine(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES user(id) ON DELETE CASCADE,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (routine_id, user_id)
        );

        CREATE INDEX IF NOT EXISTS idx_sent_email_message_id ON sent_email(message_id);
        CREATE INDEX IF NOT EXISTS idx_sent_email_trainee ON sent_email(trainee_id);
        CREATE INDEX IF NOT EXISTS idx_routine_assignment_user ON routine_assignment(user_id);
    ''')

    # Migrate: add new columns to workout table
    for col, default in [('source', "'app'"), ('parse_confidence', 'NULL'), ('review_status', 'NULL')]:
        try:
            db.execute(f'SELECT {col} FROM workout LIMIT 0')
        except sqlite3.OperationalError:
            db.execute(f'ALTER TABLE workout ADD COLUMN {col} TEXT DEFAULT {default}')

    # Migrate: add superset_group to routine_exercise
    try:
        db.execute('SELECT superset_group FROM routine_exercise LIMIT 0')
    except sqlite3.OperationalError:
        db.execute('ALTER TABLE routine_exercise ADD COLUMN superset_group INTEGER DEFAULT NULL')

    # Migrate: move routine.assigned_to data into routine_assignment junction table
    migrated = db.execute(
        'SELECT COUNT(*) FROM routine WHERE assigned_to IS NOT NULL'
    ).fetchone()[0]
    if migrated > 0:
        db.execute('''
            INSERT OR IGNORE INTO routine_assignment (routine_id, user_id)
            SELECT id, assigned_to FROM routine WHERE assigned_to IS NOT NULL
        ''')
        db.execute('UPDATE routine SET assigned_to = NULL WHERE assigned_to IS NOT NULL')

    # Seed exercises if empty
    count = db.execute('SELECT COUNT(*) FROM exercise WHERE created_by IS NULL').fetchone()[0]
    if count == 0:
        for ex in EXERCISES:
            db.execute(
                'INSERT INTO exercise (name, muscle_group, equipment, created_by) VALUES (?, ?, ?, NULL)',
                (ex['name'], ex['muscle_group'], ex['equipment'])
            )
    db.commit()
