from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from auth import login_required, get_current_user
from models import (
    create_workout, get_workout, get_active_workout, finish_workout, discard_workout,
    get_workout_history, add_workout_set, update_workout_set, delete_workout_set,
    get_workout_sets, get_last_performance, get_exercise_progress, get_exercises,
    get_exercise, get_routine, get_workout_exercises
)

workout_bp = Blueprint('workout', __name__)


@workout_bp.route('/')
@login_required
def dashboard():
    user = get_current_user()
    if user['role'] == 'trainer':
        return redirect(url_for('trainer.dashboard'))
    active = get_active_workout(user['id'])
    history = get_workout_history(user['id'], limit=5)
    return render_template('dashboard.html', active_workout=active, recent_workouts=history)


@workout_bp.route('/workout/start', methods=['POST'])
@login_required
def start_workout():
    user = get_current_user()
    active = get_active_workout(user['id'])
    if active:
        return redirect(url_for('workout.active_workout'))

    routine_id = request.form.get('routine_id')
    workout = create_workout(user['id'], routine_id=routine_id if routine_id else None)

    # Pre-fill from routine
    if routine_id:
        routine = get_routine(int(routine_id))
        if routine:
            for ex in routine['exercises']:
                for s in range(1, (ex['target_sets'] or 3) + 1):
                    add_workout_set(
                        workout['id'], ex['exercise_id'], s,
                        reps=ex['target_reps'], weight=ex['target_weight']
                    )
            # Store superset mapping in session for active workout display
            ss_map = {}
            for ex in routine['exercises']:
                if ex.get('superset_group'):
                    ss_map[str(ex['exercise_id'])] = ex['superset_group']
            if ss_map:
                session['superset_map'] = ss_map

    return redirect(url_for('workout.active_workout'))


@workout_bp.route('/workout/active')
@login_required
def active_workout():
    user = get_current_user()
    active = get_active_workout(user['id'])
    if not active:
        return redirect(url_for('workout.dashboard'))

    # Group sets by exercise
    exercises = {}
    for s in active['sets']:
        eid = s['exercise_id']
        if eid not in exercises:
            exercises[eid] = {
                'id': eid,
                'name': s['exercise_name'],
                'muscle_group': s['muscle_group'],
                'equipment': s['equipment'],
                'sets': [],
                'last_performance': get_last_performance(user['id'], eid)
            }
        exercises[eid]['sets'].append(s)

    # Get superset mapping from session (set when starting from routine)
    superset_map = session.get('superset_map', {})

    return render_template('workout_active.html', workout=active, exercises=exercises, superset_map=superset_map)


@workout_bp.route('/workout/<int:workout_id>/add-exercise', methods=['POST'])
@login_required
def add_exercise_to_workout(workout_id):
    exercise_id = request.form.get('exercise_id', type=int)
    if not exercise_id:
        return '', 400
    user = get_current_user()
    workout = get_workout(workout_id)
    if not workout or workout['user_id'] != user['id']:
        return '', 403

    # Get last performance for pre-fill
    last = get_last_performance(user['id'], exercise_id)

    # Add 3 default sets
    for i in range(1, 4):
        reps = last[i-1]['reps'] if i <= len(last) else None
        weight = last[i-1]['weight'] if i <= len(last) else None
        add_workout_set(workout_id, exercise_id, i, reps=reps, weight=weight)

    # Return updated exercise block
    exercise = get_exercise(exercise_id)
    sets = [dict(s) for s in get_workout_sets(workout_id) if s['exercise_id'] == exercise_id]
    return render_template('partials/exercise_block.html',
                           ex={
                               'id': exercise_id,
                               'name': exercise['name'],
                               'muscle_group': exercise['muscle_group'],
                               'equipment': exercise['equipment'],
                               'sets': sets,
                               'last_performance': last
                           },
                           workout=workout)


@workout_bp.route('/workout/<int:workout_id>/add-set', methods=['POST'])
@login_required
def add_set(workout_id):
    exercise_id = request.form.get('exercise_id', type=int)
    user = get_current_user()
    workout = get_workout(workout_id)
    if not workout or workout['user_id'] != user['id']:
        return '', 403

    # Find next set number for this exercise
    existing = [s for s in workout['sets'] if s['exercise_id'] == exercise_id]
    next_num = len(existing) + 1

    set_id = add_workout_set(workout_id, exercise_id, next_num)
    new_set = {'id': set_id, 'set_number': next_num, 'reps': None, 'weight': None, 'rpe': None, 'set_type': 'normal', 'exercise_id': exercise_id}
    return render_template('partials/set_row.html', s=new_set, workout_id=workout_id)


@workout_bp.route('/workout/set/<int:set_id>', methods=['PUT'])
@login_required
def update_set(set_id):
    # Parse form values — treat empty strings as None
    reps_str = request.form.get('reps', '').strip()
    weight_str = request.form.get('weight', '').strip()
    rpe_str = request.form.get('rpe', '').strip()
    set_type = request.form.get('set_type')

    reps = int(reps_str) if reps_str else None
    weight = float(weight_str) if weight_str else None
    rpe = float(rpe_str) if rpe_str else None

    # Always update all fields (even None) to allow clearing values
    from database import get_db
    db = get_db()
    db.execute(
        'UPDATE workout_set SET reps = ?, weight = ?, rpe = ? WHERE id = ?',
        (reps, weight, rpe, set_id)
    )
    if set_type:
        db.execute('UPDATE workout_set SET set_type = ? WHERE id = ?', (set_type, set_id))
    db.commit()
    return '', 204


@workout_bp.route('/workout/set/<int:set_id>', methods=['DELETE'])
@login_required
def remove_set(set_id):
    delete_workout_set(set_id)
    return '', 200


@workout_bp.route('/workout/<int:workout_id>/finish', methods=['POST'])
@login_required
def finish(workout_id):
    user = get_current_user()
    workout = get_workout(workout_id)
    if not workout or workout['user_id'] != user['id']:
        return '', 403
    notes = request.form.get('notes', '')
    finish_workout(workout_id, notes=notes)
    session.pop('superset_map', None)
    flash('Workout gespeichert!', 'success')
    return redirect(url_for('workout.dashboard'))


@workout_bp.route('/workout/<int:workout_id>/discard', methods=['POST'])
@login_required
def discard(workout_id):
    user = get_current_user()
    workout = get_workout(workout_id)
    if not workout or workout['user_id'] != user['id']:
        return '', 403
    discard_workout(workout_id)
    session.pop('superset_map', None)
    flash('Workout verworfen.', 'success')
    return redirect(url_for('workout.dashboard'))


@workout_bp.route('/workout/<int:workout_id>/duplicate')
@login_required
def duplicate(workout_id):
    """Show preview page with adjustable weight/reps/sets before duplicating."""
    user = get_current_user()
    source = get_workout(workout_id)
    if not source:
        flash('Workout nicht gefunden.', 'danger')
        return redirect(url_for('workout.history'))
    if source['user_id'] != user['id'] and user['role'] != 'trainer':
        return '', 403

    active = get_active_workout(user['id'])
    if active:
        flash('Du hast bereits ein aktives Workout. Beende es zuerst.', 'warning')
        return redirect(url_for('workout.detail', workout_id=workout_id))

    # Group sets by exercise for the preview
    exercises = {}
    for s in source['sets']:
        eid = s['exercise_id']
        if eid not in exercises:
            exercises[eid] = {
                'id': eid,
                'name': s['exercise_name'],
                'muscle_group': s['muscle_group'],
                'sets': [],
                'num_sets': 0,
            }
        exercises[eid]['sets'].append(s)
        exercises[eid]['num_sets'] += 1

    return render_template('workout_duplicate.html', source=source, exercises=exercises)


@workout_bp.route('/workout/<int:workout_id>/duplicate', methods=['POST'])
@login_required
def duplicate_execute(workout_id):
    """Create the duplicated workout with optional adjustments."""
    user = get_current_user()
    source = get_workout(workout_id)
    if not source:
        flash('Workout nicht gefunden.', 'danger')
        return redirect(url_for('workout.history'))
    if source['user_id'] != user['id'] and user['role'] != 'trainer':
        return '', 403

    active = get_active_workout(user['id'])
    if active:
        flash('Du hast bereits ein aktives Workout. Beende es zuerst.', 'warning')
        return redirect(url_for('workout.detail', workout_id=workout_id))

    new_workout = create_workout(user['id'])

    # Group source sets by exercise
    exercises = {}
    for s in source['sets']:
        eid = s['exercise_id']
        if eid not in exercises:
            exercises[eid] = []
        exercises[eid].append(s)

    # Apply adjustments per exercise
    for eid_str, sets in exercises.items():
        eid = int(eid_str) if isinstance(eid_str, str) else eid_str
        # Read adjustments from form (optional)
        weight_adj = request.form.get(f'weight_{eid}', '').strip()
        reps_adj = request.form.get(f'reps_{eid}', '').strip()
        sets_adj = request.form.get(f'sets_{eid}', '').strip()

        target_weight = float(weight_adj) if weight_adj else None
        target_reps = int(reps_adj) if reps_adj else None
        num_sets = int(sets_adj) if sets_adj else len(sets)

        for i in range(num_sets):
            s = sets[i] if i < len(sets) else sets[-1]
            add_workout_set(
                new_workout['id'], eid, i + 1,
                reps=target_reps if target_reps is not None else s['reps'],
                weight=target_weight if target_weight is not None else s['weight'],
                rpe=s.get('rpe'),
                set_type=s.get('set_type', 'normal')
            )

    flash('Workout gestartet!', 'success')
    return redirect(url_for('workout.active_workout'))


@workout_bp.route('/workout/history')
@login_required
def history():
    user = get_current_user()
    target_user_id = user['id']
    # Trainer can view trainee history
    trainee_id = request.args.get('trainee_id', type=int)
    trainee_name = None
    if trainee_id and user['role'] == 'trainer':
        target_user_id = trainee_id
        from models import get_user
        trainee = get_user(trainee_id)
        trainee_name = trainee['name'] if trainee else None

    workouts = get_workout_history(target_user_id, limit=50)
    return render_template('workout_history.html', workouts=workouts, trainee_name=trainee_name)


@workout_bp.route('/workout/<int:workout_id>')
@login_required
def detail(workout_id):
    user = get_current_user()
    workout = get_workout(workout_id)
    if not workout:
        flash('Workout nicht gefunden.', 'danger')
        return redirect(url_for('workout.history'))

    # Allow trainer to view trainee workouts
    if workout['user_id'] != user['id'] and user['role'] != 'trainer':
        return '', 403

    # Group sets by exercise
    exercises = {}
    for s in workout['sets']:
        eid = s['exercise_id']
        if eid not in exercises:
            exercises[eid] = {
                'name': s['exercise_name'],
                'muscle_group': s['muscle_group'],
                'sets': []
            }
        exercises[eid]['sets'].append(s)

    return render_template('workout_detail.html', workout=workout, exercises=exercises)


@workout_bp.route('/api/exercise-progress/<int:exercise_id>')
@login_required
def exercise_progress_api(exercise_id):
    user = get_current_user()
    target_user_id = user['id']
    trainee_id = request.args.get('trainee_id', type=int)
    if trainee_id and user['role'] == 'trainer':
        target_user_id = trainee_id
    data = get_exercise_progress(target_user_id, exercise_id)
    return jsonify(data)


@workout_bp.route('/api/exercise-picker')
@login_required
def exercise_picker():
    user = get_current_user()
    muscle_group = request.args.get('muscle_group', '')
    search = request.args.get('search', '')
    exercises = get_exercises(
        muscle_group=muscle_group if muscle_group else None,
        search=search if search else None,
        created_by=user['id']
    )
    workout_id = request.args.get('workout_id', type=int)
    return render_template('partials/exercise_picker.html', exercises=exercises, workout_id=workout_id)
