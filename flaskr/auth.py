import re
import secrets
import sqlite3

from flask import Blueprint, abort, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import create_user, get_user_by_email, get_user_by_id

bp = Blueprint('auth', __name__)
EMAIL_PATTERN = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')


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
    user = get_user_by_email(email)

    if user is None or not check_password_hash(user['password_hash'], password):
        return render_template(
            'auth.html',
            error='メールアドレスまたはパスワードが正しくありません。',
            active_form='login',
            login_email=email,
            csrf_token=get_csrf_token(),
        ), 400

    session.clear()
    session['user_id'] = user['id']
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
    if len(password) < 8:
        return 'パスワードは8文字以上で入力してください。'
    return None


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
