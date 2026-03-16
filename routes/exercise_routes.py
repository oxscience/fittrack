from flask import Blueprint, render_template, request, redirect, url_for, flash
from auth import login_required, get_current_user
from models import get_exercises, create_exercise

exercise_bp = Blueprint('exercise', __name__)

MUSCLE_GROUPS = ['chest', 'back', 'shoulders', 'arms', 'legs', 'core', 'cardio']
EQUIPMENT = ['barbell', 'dumbbell', 'machine', 'bodyweight', 'cable', 'kettlebell', 'other']

MUSCLE_GROUP_LABELS = {
    'chest': 'Brust', 'back': 'Rücken', 'shoulders': 'Schultern',
    'arms': 'Arme', 'legs': 'Beine', 'core': 'Core', 'cardio': 'Cardio'
}

EQUIPMENT_LABELS = {
    'barbell': 'Langhantel', 'dumbbell': 'Kurzhantel', 'machine': 'Maschine',
    'bodyweight': 'Körpergewicht', 'cable': 'Kabelzug', 'kettlebell': 'Kettlebell', 'other': 'Sonstige'
}


@exercise_bp.route('/exercises')
@login_required
def index():
    user = get_current_user()
    muscle_group = request.args.get('muscle_group', '')
    equipment = request.args.get('equipment', '')
    search = request.args.get('search', '')
    exercises = get_exercises(
        muscle_group=muscle_group if muscle_group else None,
        equipment=equipment if equipment else None,
        search=search if search else None,
        created_by=user['id']
    )
    return render_template('exercises.html',
                           exercises=exercises,
                           muscle_groups=MUSCLE_GROUPS,
                           equipment_list=EQUIPMENT,
                           muscle_group_labels=MUSCLE_GROUP_LABELS,
                           equipment_labels=EQUIPMENT_LABELS,
                           selected_muscle_group=muscle_group,
                           selected_equipment=equipment,
                           search_query=search)


@exercise_bp.route('/exercises/create', methods=['POST'])
@login_required
def create():
    user = get_current_user()
    name = request.form.get('name', '').strip()
    muscle_group = request.form.get('muscle_group', '')
    equipment = request.form.get('equipment', 'bodyweight')
    if not name or not muscle_group:
        flash('Name und Muskelgruppe sind erforderlich.', 'danger')
        return redirect(url_for('exercise.index'))
    create_exercise(name, muscle_group, equipment, user['id'])
    flash(f'Übung "{name}" erstellt.', 'success')
    return redirect(url_for('exercise.index'))
