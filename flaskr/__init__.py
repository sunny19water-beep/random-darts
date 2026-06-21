import os
from flask import Flask, abort, redirect, render_template, request, url_for
from .app import draw_advanced_numbers, draw_number
from .db import init_app as init_db_app
from .db import save_result

app = Flask(__name__)
app.config['DATABASE'] = os.path.join(app.instance_path, 'darts.sqlite')
os.makedirs(app.instance_path, exist_ok=True)
init_db_app(app)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/result')
def result():
    return render_template('result.html')


@app.route('/next')
def next_page():
    random_number = draw_number()
    return render_template('second.html', random_number=random_number)

@app.post('/success')
def success():
    number = validate_number(request.form.get('number'))
    success_count = validate_success_count(request.form.get('count', type=int))
    save_result(number, success_count, mode='normal')
    return redirect(url_for('next_page'))

@app.route('/Advanced')
@app.route('/advanced')
def advanced_page():
    random_number, bed_number = draw_advanced_numbers()
    return render_template('Advanced.html', random_number=random_number, bed_number=bed_number)

@app.post('/Advanced_success')
@app.post('/advanced/success')
def advanced_success():
    number = validate_number(request.form.get('number'))
    success_count = validate_success_count(request.form.get('count', type=int))
    bed = request.form.get('bed')
    if bed not in {'Single', 'Double', 'Triple', 'Outer', 'Inner'}:
        abort(400)

    save_result(number, success_count, mode='advanced', bed=bed)
    return redirect(url_for('advanced_page'))


def validate_number(number):
    if number == 'bull':
        return number

    try:
        parsed_number = int(number)
    except (TypeError, ValueError):
        abort(400)

    if not 1 <= parsed_number <= 20:
        abort(400)
    return parsed_number


def validate_success_count(success_count):
    if success_count not in range(4):
        abort(400)
    return success_count
