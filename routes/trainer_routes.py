from flask import Blueprint, render_template, request, redirect, url_for, flash
from auth import login_required, role_required, get_current_user
from models import (
    get_trainees, get_trainee_stats, get_workout_history, get_user,
    update_trainee_notes, get_trainer_invites, get_exercises, get_exercise_progress,
    get_pending_review_workouts, update_workout_review, get_workout, discard_workout
)

trainer_bp = Blueprint('trainer', __name__)


@trainer_bp.route('/trainer')
@login_required
@role_required('trainer')
def dashboard():
    user = get_current_user()
    trainees = get_trainees(user['id'])
    for t in trainees:
        t['stats'] = get_trainee_stats(t['id'])
    invites = get_trainer_invites(user['id'])
    pending_reviews = get_pending_review_workouts(trainer_id=user['id'])
    return render_template('trainer_dashboard.html', trainees=trainees, invites=invites, pending_reviews=pending_reviews)


@trainer_bp.route('/trainer/trainee/<int:trainee_id>')
@login_required
@role_required('trainer')
def trainee_detail(trainee_id):
    user = get_current_user()
    trainees = get_trainees(user['id'])
    trainee_ids = [t['id'] for t in trainees]
    if trainee_id not in trainee_ids:
        flash('Kein Zugriff auf diesen Trainee.', 'danger')
        return redirect(url_for('trainer.dashboard'))

    trainee = get_user(trainee_id)
    stats = get_trainee_stats(trainee_id)
    workouts = get_workout_history(trainee_id, limit=20)
    notes = next((t['notes'] for t in trainees if t['id'] == trainee_id), '')

    # Get exercises the trainee has done for progress charts
    from database import get_db
    db = get_db()
    trained_exercises = db.execute('''
        SELECT DISTINCT e.id, e.name, e.muscle_group
        FROM workout_set ws
        JOIN exercise e ON e.id = ws.exercise_id
        JOIN workout w ON w.id = ws.workout_id
        WHERE w.user_id = ? AND w.finished_at IS NOT NULL
        ORDER BY e.name
    ''', (trainee_id,)).fetchall()
    trained_exercises = [dict(e) for e in trained_exercises]

    return render_template('trainee_detail.html',
                           trainee=trainee, stats=stats, workouts=workouts,
                           notes=notes, trained_exercises=trained_exercises)


@trainer_bp.route('/trainer/trainee/<int:trainee_id>/notes', methods=['POST'])
@login_required
@role_required('trainer')
def update_notes(trainee_id):
    user = get_current_user()
    notes = request.form.get('notes', '')
    update_trainee_notes(user['id'], trainee_id, notes)
    flash('Notizen gespeichert.', 'success')
    return redirect(url_for('trainer.trainee_detail', trainee_id=trainee_id))


@trainer_bp.route('/trainer/review')
@login_required
@role_required('trainer')
def review_queue():
    user = get_current_user()
    workouts = get_pending_review_workouts(trainer_id=user['id'])
    for w in workouts:
        full = get_workout(w['id'])
        w['sets'] = full['sets'] if full else []
    return render_template('trainer_review.html', workouts=workouts)


@trainer_bp.route('/trainer/review/<int:workout_id>', methods=['POST'])
@login_required
@role_required('trainer')
def review_workout(workout_id):
    action = request.form.get('action')
    if action == 'approve':
        update_workout_review(workout_id, 'approved')
        flash('Workout bestätigt.', 'success')
    elif action == 'reject':
        discard_workout(workout_id)
        flash('Workout verworfen.', 'success')
    return redirect(url_for('trainer.review_queue'))
