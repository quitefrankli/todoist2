import os
import random
import click
import logging
import flask
import flask_login

from signal import signal, SIGTERM
from typing import *
from pathlib import Path
from flask import render_template, send_from_directory, request
from flask_bootstrap import Bootstrap5
from datetime import datetime, date
from logging.handlers import RotatingFileHandler

from web_app.users import User
from web_app.data_interface import DataInterface
from web_app.app_data import TopLevelData, GoalState, Goal
from web_app.visualiser import plot_velocity
from web_app.helpers import from_req, limiter, admin_only
from web_app.app import app


# app = Flask(__name__)
app.secret_key = os.urandom(24)
from web_app.api.goals_api import goals_api
from web_app.api.account_api import account_api
from web_app.api.metrics_api import metrics_api
app.register_blueprint(goals_api)
app.register_blueprint(account_api)
app.register_blueprint(metrics_api)

bootstrap = Bootstrap5(app)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


def get_default_redirect():
    return flask.redirect(flask.url_for('home'))

def get_random_image() -> Path:
    BASE_DIR = Path(os.environ["RANDOM_IMAGES_DIR"] if "RANDOM_IMAGES_DIR" in os.environ else "resources")
    images = list(BASE_DIR.glob("*.jpeg"))

    return random.choice(images).absolute()

def get_summary_goals(user: User) -> List[Tuple[str, List[Goal]]]:
    now = datetime.now()
    def should_render(goal: Goal) -> bool:
        # # TODO: add support for parent/children goals
        # if goal.parent or goal.children:
        #     return False
        if goal.recurrence:
            return False
        if goal.state not in (GoalState.ACTIVE, GoalState.COMPLETED):
            return False
        # hides goals that have been completed for a while
        if goal.state == GoalState.COMPLETED and (now - goal.completion_date).days > 2:
            return False
        return True
    
    goals = list(DataInterface.instance().load_data(user).goals.values())
    goals = [goal for goal in goals if should_render(goal)]
    goals.sort(key=lambda goal: goal.creation_date.timestamp(), reverse=True)

    goal_blocks = []
    last_date_label: date = None
    for goal in goals:
        goal_date = goal.creation_date.date()
        if last_date_label != goal_date:
            last_date_label = goal_date
            goal_blocks.append((last_date_label.strftime("%d/%m/%Y"), [goal]))
        else:
            goal_blocks[-1] = (goal_blocks[-1][0], [goal] + goal_blocks[-1][1])

    return goal_blocks

@app.route('/')
@app.route('/home')
@flask_login.login_required
@limiter.limit("2/second")
def home():
    dated_goal_blocks = get_summary_goals(flask_login.current_user)
    return render_template('index.html', dated_goal_blocks=dated_goal_blocks)

@app.route('/completed_goals')
@flask_login.login_required
@limiter.limit("2/second")
def completed_goals():
    user = flask_login.current_user
    goals = list(DataInterface.instance().load_data(user).goals.values())
    goals = [goal for goal in goals if goal.state == GoalState.COMPLETED]
    goals.sort(key=lambda goal: goal.completion_date.timestamp(), reverse=True)

    goal_blocks = []
    last_date_label: date = None
    for goal in goals:
        goal_date = goal.completion_date.date()
        if last_date_label != goal_date:
            last_date_label = goal_date
            goal_blocks.append((last_date_label.strftime("%d/%m/%Y"), [goal]))
        else:
            goal_blocks[-1] = (goal_blocks[-1][0], [goal] + goal_blocks[-1][1])
    return render_template('completed_goals_page.html', dated_goal_blocks=goal_blocks)

@app.route('/resources/<path:filename>')
@flask_login.login_required
@limiter.limit("2/second")
@admin_only('home')
def static_file(filename):
    image = get_random_image()
    logging.info(f"Sending {image} for {filename}")
    return send_from_directory(directory=image.parent, path=image.name)

@app.route('/visualise/goal_velocity', methods=['GET'])
@flask_login.login_required
@limiter.limit("1/second", key_func=lambda: flask_login.current_user.id)
def visualise_goal_velocity():
    tld = DataInterface.instance().load_data(flask_login.current_user)
    goals = [goal for goal in tld.goals.values() if goal.state == GoalState.COMPLETED]
    if len(goals) < 2:
        flask.flash('Too few completeed goals to visualise', category='error')
        return get_default_redirect()
    
    try:
        embeddable_plotly_html = plot_velocity(goals)
    except Exception as e:
        logging.error(f"Failed to plot velocity: {e}")
        flask.flash('Failed to plot velocity, try completing more goals and/or wait a couple days', category='error')
        return get_default_redirect()

    return render_template('goal_velocity.html', plot=embeddable_plotly_html)

@app.before_request
def before_request():
    message = f"Processing request: client={request.remote_addr}, path={request.path}, method={request.method}"

    if request.method == 'POST':
        if request.is_json:
            message += f", json={request.get_json()}"
        elif request.form:
            message += f", form={request.form}"

    logging.info(message)

@app.route('/debug')
@flask_login.login_required
@admin_only('home')
def debug():
    return render_template('debug.html')

def graceful_shutdown(signum=None, frame=None):
    logging.info("Shutting down server")
    exit(0)

@app.route('/shutdown')
@flask_login.login_required
@admin_only('home')
def shutdown():
    graceful_shutdown()
    return "Shutting down..."

@app.route('/backup', methods=['GET'])
@flask_login.login_required
@admin_only('home')
def backup():
    instance = DataInterface.instance()
    users = instance.load_users()
    for user in users.values():
        tld = instance.load_data(user)
        instance.backup_data(tld, user)

    flask.flash('Backup complete', category='success')

    return flask.redirect(flask.url_for('debug'))

@click.command()
@click.option('--debug', is_flag=True, help='Run the server in debug mode', default=False)
def main(debug: bool):
    log_path = Path("logs/web_app.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    rotating_log_handler = RotatingFileHandler(str(log_path),
                                               maxBytes=int(1e6),
                                               backupCount=10)
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO, 
                        handlers=[] if debug else [rotating_log_handler])
    
    DataInterface.create_instance(debug)

    logging.info("Starting server")

    signal(SIGTERM, graceful_shutdown)

    app.run(host='0.0.0.0', port=80, debug=debug)

if __name__ == '__main__':
    main()