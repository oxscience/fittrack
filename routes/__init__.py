from flask import Flask


def register_blueprints(app: Flask):
    from routes.auth_routes import auth_bp
    from routes.workout_routes import workout_bp
    from routes.exercise_routes import exercise_bp
    from routes.routine_routes import routine_bp
    from routes.trainer_routes import trainer_bp
    from routes.setup_routes import setup_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(workout_bp)
    app.register_blueprint(exercise_bp)
    app.register_blueprint(routine_bp)
    app.register_blueprint(trainer_bp)
    app.register_blueprint(setup_bp)
