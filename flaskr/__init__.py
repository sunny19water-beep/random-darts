import os
import secrets

from flask import Flask, abort, redirect, render_template, request, session, url_for
from .app import draw_advanced_numbers, draw_number
from .db import init_app as init_db_app
from .db import get_results, save_result

RESULT_RANGES = {'3': 3, '10': 10, '50': 50, '100': 100, 'all': None}
MIN_TOTAL_THROWS_FOR_ANALYSIS = 50
MIN_THROWS_PER_NUMBER = 9
MAX_PENDING_TARGETS = 10

app = Flask(__name__)
app.config['DATABASE'] = os.path.join(app.instance_path, 'darts.sqlite')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
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
    selected_range = request.args.get('range', '10')
    if selected_range not in RESULT_RANGES:
        selected_range = '10'

    results = get_results(RESULT_RANGES[selected_range])
    all_results = get_results()
    summary = summarize_results(results)
    number_stats = summarize_by_number(results)
    all_number_stats = summarize_by_number(all_results)
    total_throws = len(all_results) * 3
    eligible_number_stats = [
        stat for stat in all_number_stats
        if stat['throws'] >= MIN_THROWS_PER_NUMBER
    ]
    weak_numbers = (
        find_weak_numbers(eligible_number_stats)
        if total_throws >= MIN_TOTAL_THROWS_FOR_ANALYSIS
        else []
    )

    chart_data = {
        'numbers': {
            'labels': [stat['number'] for stat in number_stats],
            'rates': [stat['success_rate'] for stat in number_stats],
        },
        'trend': {
            'labels': list(range(1, len(results) + 1)),
            'rates': [round(row['success_count'] / 3 * 100, 1) for row in results],
        },
    }

    return render_template(
        'result.html',
        selected_range=selected_range,
        summary=summary,
        weak_numbers=weak_numbers,
        total_throws=total_throws,
        min_total_throws=MIN_TOTAL_THROWS_FOR_ANALYSIS,
        min_throws_per_number=MIN_THROWS_PER_NUMBER,
        throws_until_analysis=max(0, MIN_TOTAL_THROWS_FOR_ANALYSIS - total_throws),
        chart_data=chart_data,
    )


@app.route('/next')
def next_page():
    random_number = draw_number()
    target_token = create_pending_target('normal', random_number)
    return render_template(
        'second.html',
        random_number=random_number,
        target_token=target_token,
    )

@app.post('/success')
def success():
    success_count = validate_success_count(request.form.get('count', type=int))
    target = consume_pending_target(request.form.get('target_token'), 'normal')
    number = validate_number(target['number'])
    save_result(number, success_count, mode='normal')
    return redirect(url_for('next_page'))

@app.route('/Advanced')
@app.route('/advanced')
def advanced_page():
    random_number, bed_number = draw_advanced_numbers()
    target_token = create_pending_target('advanced', random_number, bed_number)
    return render_template(
        'Advanced.html',
        random_number=random_number,
        bed_number=bed_number,
        target_token=target_token,
    )

@app.post('/Advanced_success')
@app.post('/advanced/success')
def advanced_success():
    success_count = validate_success_count(request.form.get('count', type=int))
    target = consume_pending_target(request.form.get('target_token'), 'advanced')
    number = validate_number(target['number'])
    bed = target['bed']
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


def create_pending_target(mode, number, bed=None):
    pending_targets = dict(session.get('pending_targets', {}))
    while len(pending_targets) >= MAX_PENDING_TARGETS:
        pending_targets.pop(next(iter(pending_targets)))

    token = secrets.token_urlsafe(16)
    pending_targets[token] = {'mode': mode, 'number': number, 'bed': bed}
    session['pending_targets'] = pending_targets
    return token


def consume_pending_target(token, expected_mode):
    pending_targets = dict(session.get('pending_targets', {}))
    target = pending_targets.get(token)
    if target is None or target.get('mode') != expected_mode:
        abort(400)

    pending_targets.pop(token)
    session['pending_targets'] = pending_targets
    return target


def summarize_results(results):
    rounds = len(results)
    total_throws = rounds * 3
    successes = sum(row['success_count'] for row in results)
    success_rate = round(successes / total_throws * 100, 1) if total_throws else None
    return {
        'rounds': rounds,
        'total_throws': total_throws,
        'successes': successes,
        'success_rate': success_rate,
    }


def summarize_by_number(results):
    summaries = {}
    for row in results:
        number = row['number']
        if number not in summaries:
            summaries[number] = {'number': number, 'rounds': 0, 'successes': 0}
        summaries[number]['rounds'] += 1
        summaries[number]['successes'] += row['success_count']

    for summary in summaries.values():
        summary['throws'] = summary['rounds'] * 3
        summary['success_rate'] = round(
            summary['successes'] / summary['throws'] * 100,
            1,
        )

    return sorted(summaries.values(), key=number_sort_key)


def number_sort_key(summary):
    number = summary['number']
    return (1, 21) if number == 'bull' else (0, int(number))


def find_weak_numbers(number_stats):
    if not number_stats:
        return []
    lowest_rate = min(stat['success_rate'] for stat in number_stats)
    return [stat for stat in number_stats if stat['success_rate'] == lowest_rate]
