from flask import Blueprint, render_template, request, redirect, url_for, flash
from auth import login_required, get_current_user, role_required
from models import (
    create_routine, get_routine, get_routines_for_user, delete_routine,
    add_routine_exercise, clear_routine_exercises, update_routine,
    get_exercises, get_trainees, assign_routine, unassign_routine
)

routine_bp = Blueprint('routine', __name__)


@routine_bp.route('/routines')
@login_required
def index():
    user = get_current_user()
    routines = get_routines_for_user(user['id'])
    trainees = get_trainees(user['id']) if user['role'] == 'trainer' else []
    return render_template('routines.html', routines=routines, trainees=trainees)


@routine_bp.route('/routines/new')
@login_required
def new():
    user = get_current_user()
    exercises = get_exercises(created_by=user['id'])
    return render_template('routine_editor.html', routine=None, exercises=exercises)


@routine_bp.route('/routines', methods=['POST'])
@login_required
def create():
    user = get_current_user()
    name = request.form.get('name', '').strip()
    if not name:
        flash('Name ist erforderlich.', 'danger')
        return redirect(url_for('routine.new'))

    routine = create_routine(name, user['id'])

    # Add exercises from form
    exercise_ids = request.form.getlist('exercise_id[]', type=int)
    target_sets_list = request.form.getlist('target_sets[]', type=int)
    target_reps_list = request.form.getlist('target_reps[]', type=int)
    target_weight_list = request.form.getlist('target_weight[]')
    superset_groups = request.form.getlist('superset_group[]')

    for i, eid in enumerate(exercise_ids):
        sets = target_sets_list[i] if i < len(target_sets_list) else 3
        reps = target_reps_list[i] if i < len(target_reps_list) else 10
        weight_str = target_weight_list[i] if i < len(target_weight_list) else ''
        weight = float(weight_str) if weight_str else None
        sg_str = superset_groups[i] if i < len(superset_groups) else ''
        sg = int(sg_str) if sg_str else None
        add_routine_exercise(routine['id'], eid, i, target_sets=sets, target_reps=reps, target_weight=weight, superset_group=sg)

    flash(f'Training "{name}" erstellt.', 'success')
    return redirect(url_for('routine.index'))


@routine_bp.route('/routines/<int:routine_id>')
@login_required
def detail(routine_id):
    user = get_current_user()
    routine = get_routine(routine_id)
    if not routine:
        flash('Training nicht gefunden.', 'danger')
        return redirect(url_for('routine.index'))
    exercises = get_exercises(created_by=user['id'])
    return render_template('routine_editor.html', routine=routine, exercises=exercises)


@routine_bp.route('/routines/<int:routine_id>', methods=['POST'])
@login_required
def update(routine_id):
    user = get_current_user()
    routine = get_routine(routine_id)
    if not routine or routine['created_by'] != user['id']:
        return '', 403

    name = request.form.get('name', '').strip()
    update_routine(routine_id, name=name)

    # Replace exercises
    clear_routine_exercises(routine_id)
    exercise_ids = request.form.getlist('exercise_id[]', type=int)
    target_sets_list = request.form.getlist('target_sets[]', type=int)
    target_reps_list = request.form.getlist('target_reps[]', type=int)
    target_weight_list = request.form.getlist('target_weight[]')
    superset_groups = request.form.getlist('superset_group[]')

    for i, eid in enumerate(exercise_ids):
        sets = target_sets_list[i] if i < len(target_sets_list) else 3
        reps = target_reps_list[i] if i < len(target_reps_list) else 10
        weight_str = target_weight_list[i] if i < len(target_weight_list) else ''
        weight = float(weight_str) if weight_str else None
        sg_str = superset_groups[i] if i < len(superset_groups) else ''
        sg = int(sg_str) if sg_str else None
        add_routine_exercise(routine_id, eid, i, target_sets=sets, target_reps=reps, target_weight=weight, superset_group=sg)

    flash('Training aktualisiert.', 'success')
    return redirect(url_for('routine.index'))


@routine_bp.route('/routines/<int:routine_id>/assign', methods=['POST'])
@login_required
def assign(routine_id):
    user = get_current_user()
    routine = get_routine(routine_id)
    if not routine or routine['created_by'] != user['id']:
        return '', 403
    user_id = request.form.get('user_id', type=int)
    if user_id:
        assign_routine(routine_id, user_id)
    return redirect(url_for('routine.index'))


@routine_bp.route('/routines/<int:routine_id>/unassign', methods=['POST'])
@login_required
def unassign(routine_id):
    user = get_current_user()
    routine = get_routine(routine_id)
    if not routine or routine['created_by'] != user['id']:
        return '', 403
    user_id = request.form.get('user_id', type=int)
    if user_id:
        unassign_routine(routine_id, user_id)
    return redirect(url_for('routine.index'))


@routine_bp.route('/routines/<int:routine_id>/send-email', methods=['POST'])
@login_required
def send_email(routine_id):
    user = get_current_user()
    routine = get_routine(routine_id)
    if not routine or routine['created_by'] != user['id']:
        return '', 403
    if not routine.get('assignees'):
        flash('Training ist keinem Trainee zugewiesen.', 'warning')
        return redirect(url_for('routine.index'))

    from email_service import send_training_plan
    sent_count = 0
    for trainee in routine['assignees']:
        message_id = send_training_plan(routine, trainee, routine.get('exercises', []))
        if message_id:
            sent_count += 1

    if sent_count:
        flash(f'Trainingsplan an {sent_count} Trainee(s) gesendet!', 'success')
    else:
        flash('E-Mail konnte nicht gesendet werden. Prüfe die E-Mail-Einstellungen.', 'danger')
    return redirect(url_for('routine.index'))


@routine_bp.route('/routines/<int:routine_id>/delete', methods=['POST'])
@login_required
def remove(routine_id):
    user = get_current_user()
    routine = get_routine(routine_id)
    if not routine or routine['created_by'] != user['id']:
        return '', 403
    delete_routine(routine_id)
    flash('Training gelöscht.', 'success')
    return redirect(url_for('routine.index'))
