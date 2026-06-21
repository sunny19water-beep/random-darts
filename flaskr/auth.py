import re
import secrets
import sqlite3
import time
from collections import deque
from threading import Lock

from flask import Blueprint, abort, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import create_user, get_user_by_email, get_user_by_id

bp = Blueprint('auth', __name__)
EMAIL_PATTERN = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
LOGIN_ATTEMPT_WINDOW = 15 * 60
MAX_LOGIN_ATTEMPTS_PER_ACCOUNT = 5
MAX_LOGIN_ATTEMPTS_PER_IP = 25
login_attempts = {}
login_attempts_lock = Lock()


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    g.user = get_user_by_id(user_id) if user_id is not None else None


@bp.route('/auth')
def auth_page():
    if g.user is not None:
        return redirect(url_for('index'))
    return render_template('auth.html', csrf_token=get_csrf_token())


@bp.post('/register')
def register():
    validate_csrf()
    email = request.form.get('email', '').strip().lower()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    error = validate_registration(email, username, password)

    if error is None:
        try:
            user_id = create_user(email, username, generate_password_hash(password))
        except sqlite3.IntegrityError:
            error = 'メールアドレスまたはユーザー名は既に使用されています。'
        else:
            session.clear()
            session.permanent = True
            session['user_id'] = user_id
            return redirect(url_for('index'))

    return render_template(
        'auth.html',
        error=error,
        active_form='register',
        email=email,
        username=username,
        csrf_token=get_csrf_token(),
    ), 400


@bp.post('/login')
def login():
    validate_csrf()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    ip_address = request.remote_addr or 'unknown'
    rate_limit_email = email if len(email) <= 254 else 'invalid-email'
    if is_login_limited(ip_address, rate_limit_email):
        response = render_template(
            'auth.html',
            error='ログイン試行が多すぎます。15分ほど待ってから再度お試しください。',
            active_form='login',
            login_email=email[:254],
            csrf_token=get_csrf_token(),
        )
        return response, 429, {'Retry-After': str(LOGIN_ATTEMPT_WINDOW)}

    valid_input_lengths = len(email) <= 254 and len(password) <= 128
    user = get_user_by_email(email) if valid_input_lengths else None

    if user is None or not check_password_hash(user['password_hash'], password):
        record_login_failure(ip_address, rate_limit_email)
        return render_template(
            'auth.html',
            error='メールアドレスまたはパスワードが正しくありません。',
            active_form='login',
            login_email=email[:254],
            csrf_token=get_csrf_token(),
        ), 400

    session.clear()
    session.permanent = True
    session['user_id'] = user['id']
    clear_login_failures(ip_address, rate_limit_email)
    return redirect(url_for('index'))


@bp.post('/logout')
def logout():
    validate_csrf()
    session.clear()
    return redirect(url_for('index'))


def validate_registration(email, username, password):
    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        return '有効なメールアドレスを入力してください。'
    if not 2 <= len(username) <= 30:
        return 'ユーザー名は2〜30文字で入力してください。'
    if any(character.isspace() for character in username):
        return 'ユーザー名には空白文字を使用できません。'
    if not 10 <= len(password) <= 128:
        return 'パスワードは10〜128文字で入力してください。'
    if not username.isprintable():
        return 'ユーザー名に制御文字を使用できません。'
    return None


def _attempt_keys(ip_address, email):
    return (f'ip:{ip_address}', f'account:{ip_address}:{email}')


def _prune_attempts(attempts, now):
    cutoff = now - LOGIN_ATTEMPT_WINDOW
    while attempts and attempts[0] <= cutoff:
        attempts.popleft()


def is_login_limited(ip_address, email):
    now = time.monotonic()
    ip_key, account_key = _attempt_keys(ip_address, email)
    with login_attempts_lock:
        for key in (ip_key, account_key):
            attempts = login_attempts.get(key)
            if attempts is not None:
                _prune_attempts(attempts, now)
                if not attempts:
                    login_attempts.pop(key, None)
        return (
            len(login_attempts.get(ip_key, ())) >= MAX_LOGIN_ATTEMPTS_PER_IP
            or len(login_attempts.get(account_key, ()))
            >= MAX_LOGIN_ATTEMPTS_PER_ACCOUNT
        )


def record_login_failure(ip_address, email):
    now = time.monotonic()
    with login_attempts_lock:
        for key in _attempt_keys(ip_address, email):
            attempts = login_attempts.setdefault(key, deque())
            _prune_attempts(attempts, now)
            attempts.append(now)


def clear_login_failures(ip_address, email):
    _, account_key = _attempt_keys(ip_address, email)
    with login_attempts_lock:
        login_attempts.pop(account_key, None)


def get_csrf_token():
    token = session.get('csrf_token')
    if token is None:
        token = secrets.token_urlsafe(32)
        session['csrf_token'] = token
    return token


def validate_csrf():
    expected = session.get('csrf_token', '')
    received = request.form.get('csrf_token', '')
    if not expected or not secrets.compare_digest(expected, received):
        abort(400)
