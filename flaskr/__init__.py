import os
import secrets
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import Flask, abort, g, redirect, render_template, request, session, url_for
from .app import CRICKET_NUMBERS, draw_advanced_numbers, draw_cricket_number, draw_number
from .auth import bp as auth_bp
from .auth import get_csrf_token
from .db import init_app as init_db_app
from .db import get_db, get_rankings, get_results, save_result

RESULT_RANGES = {'3': 3, '10': 10, '50': 50, '100': 100, 'all': None}
MIN_TOTAL_THROWS_FOR_ANALYSIS = 50
WORST_NUMBER_LIMIT = 7
MAX_PENDING_TARGETS = 10

app = Flask(__name__)
is_production = os.environ.get('APP_ENV') == 'production'
secret_key = os.environ.get('SECRET_KEY')
if is_production and not secret_key:
    raise RuntimeError('SECRET_KEY must be set in production.')

database_path = os.environ.get(
    'DATABASE_PATH',
    os.path.join(app.instance_path, 'darts.sqlite'),
)
os.makedirs(os.path.dirname(database_path) or app.instance_path, exist_ok=True)
app.config.update(
    DATABASE=database_path,
    SECRET_KEY=secret_key or secrets.token_hex(32),
    MAX_CONTENT_LENGTH=64 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=is_production,
)
init_db_app(app)
app.register_blueprint(auth_bp)


@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    if is_production:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000'
    return response


@app.get('/health')
def health():
    get_db().execute('SELECT 1').fetchone()
    return {'status': 'ok'}

@app.route('/')
def index():
    return render_template('index.html', csrf_token=get_csrf_token())


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/result')
def result():
    selected_range = request.args.get('range', '10')
    if selected_range not in RESULT_RANGES:
        selected_range = '10'

    user_id = g.user['id'] if g.user is not None else None
    results = get_results(RESULT_RANGES[selected_range], user_id) if user_id else []
    summary = summarize_results(results)
    number_stats = summarize_by_number(results)
    weakness = get_weakness_analysis(user_id)
    week_start = get_current_week_start_utc()

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
        weak_numbers=weakness['weak_numbers'],
        total_throws=weakness['total_throws'],
        min_total_throws=MIN_TOTAL_THROWS_FOR_ANALYSIS,
        throws_until_analysis=weakness['throws_until_analysis'],
        weekly_rankings=get_rankings(week_start),
        all_time_rankings=get_rankings(),
        chart_data=chart_data,
    )


@app.route('/weakness')
def weakness_practice():
    user_id = g.user['id'] if g.user is not None else None
    weakness = get_weakness_analysis(user_id)
    if not weakness['weak_numbers']:
        return render_template(
            'weakness.html',
            target_number=None,
            total_throws=weakness['total_throws'],
            throws_until_analysis=weakness['throws_until_analysis'],
            min_total_throws=MIN_TOTAL_THROWS_FOR_ANALYSIS,
            is_authenticated=g.user is not None,
        )

    target_number = select_next_weak_number(weakness['weak_numbers'])
    target_token = create_pending_target('weakness', target_number)
    return render_template(
        'weakness.html',
        target_number=target_number,
        target_token=target_token,
        total_throws=weakness['total_throws'],
        min_total_throws=MIN_TOTAL_THROWS_FOR_ANALYSIS,
        is_authenticated=True,
    )


@app.post('/weakness/success')
def weakness_success():
    success_count = validate_success_count(request.form.get('count', type=int))
    target = consume_pending_target(request.form.get('target_token'), 'weakness')
    number = validate_number(target['number'])
    save_authenticated_result(number, success_count, mode='normal')
    advance_weakness_rotation(str(number))
    return redirect(url_for('weakness_practice'))


@app.route('/cricket')
def cricket_page():
    cricket_number = draw_cricket_number()
    target_token = create_pending_target('cricket', cricket_number)
    return render_template(
        'cricket.html',
        cricket_number=cricket_number,
        target_token=target_token,
    )


@app.post('/cricket/success')
def cricket_success():
    success_count = validate_success_count(request.form.get('count', type=int))
    target = consume_pending_target(request.form.get('target_token'), 'cricket')
    number = validate_number(target['number'])
    if number not in CRICKET_NUMBERS:
        abort(400)

    save_authenticated_result(number, success_count, mode='cricket')
    return redirect(url_for('cricket_page'))


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
    save_authenticated_result(number, success_count, mode='normal')
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

    save_authenticated_result(number, success_count, mode='advanced', bed=bed)
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


def rank_weak_numbers(number_stats):
    return sorted(
        number_stats,
        key=lambda stat: (stat['success_rate'], -stat['throws'], number_sort_key(stat)),
    )[:WORST_NUMBER_LIMIT]


def get_weakness_analysis(user_id=None):
    all_results = get_results(user_id=user_id) if user_id is not None else []
    total_throws = len(all_results) * 3
    number_stats = summarize_by_number(all_results)
    weak_numbers = (
        rank_weak_numbers(number_stats)
        if total_throws >= MIN_TOTAL_THROWS_FOR_ANALYSIS
        else []
    )
    return {
        'total_throws': total_throws,
        'throws_until_analysis': max(
            0,
            MIN_TOTAL_THROWS_FOR_ANALYSIS - total_throws,
        ),
        'weak_numbers': weak_numbers,
    }


def select_next_weak_number(weak_numbers):
    ranked_numbers = [str(stat['number']) for stat in weak_numbers]
    rotation = dict(session.get('weakness_rotation', {}))
    rotation_numbers = rotation.get('numbers', [])

    if set(rotation_numbers) != set(ranked_numbers):
        rotation_numbers = ranked_numbers
        rotation = {'numbers': rotation_numbers, 'index': 0}

    index = rotation.get('index', 0) % len(rotation_numbers)
    session['weakness_rotation'] = rotation
    return rotation_numbers[index]


def advance_weakness_rotation(completed_number):
    rotation = dict(session.get('weakness_rotation', {}))
    rotation_numbers = rotation.get('numbers', [])
    if not rotation_numbers:
        return

    index = rotation.get('index', 0) % len(rotation_numbers)
    if rotation_numbers[index] == completed_number:
        rotation['index'] = (index + 1) % len(rotation_numbers)
        session['weakness_rotation'] = rotation


def save_authenticated_result(number, success_count, mode, bed=None):
    if g.user is None:
        return None
    return save_result(
        number,
        success_count,
        mode,
        bed=bed,
        user_id=g.user['id'],
    )


def get_current_week_start_utc():
    now_jst = datetime.now(ZoneInfo('Asia/Tokyo'))
    week_start_jst = (now_jst - timedelta(days=now_jst.weekday())).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    return week_start_jst.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
