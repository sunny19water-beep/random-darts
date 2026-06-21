import sqlite3

import click
from flask import current_app, g


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')

    return g.db


def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def ensure_schema():
    db = get_db()
    with current_app.open_resource('schema.sql') as schema_file:
        schema = schema_file.read().decode('utf-8')

    table = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'throw_results'"
    ).fetchone()
    if table is not None and "'cricket'" not in table['sql']:
        db.executescript(
            f'''
            BEGIN;
            ALTER TABLE throw_results RENAME TO throw_results_legacy;
            DROP INDEX IF EXISTS idx_throw_results_user_id;
            {schema}
            INSERT INTO throw_results
                (id, user_id, number, success_count, mode, bed, created_at)
            SELECT id, user_id, number, success_count, mode, bed, created_at
            FROM throw_results_legacy;
            DROP TABLE throw_results_legacy;
            COMMIT;
            '''
        )
    else:
        db.executescript(schema)
    db.commit()


def init_db():
    db = get_db()
    db.execute('DROP TABLE IF EXISTS user_results')
    db.execute('DROP TABLE IF EXISTS users')
    db.execute('DROP TABLE IF EXISTS throw_results')
    ensure_schema()


@click.command('init-db')
def init_db_command():
    """結果データを消去し、データベースを初期化する。"""
    init_db()
    click.echo('Initialized the database.')


def save_result(number, success_count, mode, bed=None, user_id=None):
    db = get_db()
    cursor = db.execute(
        '''
        INSERT INTO throw_results
            (user_id, number, success_count, mode, bed)
        VALUES (?, ?, ?, ?, ?)
        ''',
        (user_id, str(number), success_count, mode, bed),
    )
    if user_id is not None:
        db.execute(
            'INSERT INTO user_results (user_id, result_id) VALUES (?, ?)',
            (user_id, cursor.lastrowid),
        )
    db.commit()
    return cursor.lastrowid


def get_results(limit=None, user_id=None):
    db = get_db()
    if user_id is not None:
        base_query = '''
            SELECT throw_results.*
            FROM throw_results
            JOIN user_results ON user_results.result_id = throw_results.id
            WHERE user_results.user_id = ?
        '''
        parameters = (user_id,)
    else:
        base_query = 'SELECT * FROM throw_results'
        parameters = ()

    if limit is None:
        return db.execute(f'{base_query} ORDER BY throw_results.id', parameters).fetchall()

    return db.execute(
        f'''
        SELECT *
        FROM (
            {base_query} ORDER BY throw_results.id DESC LIMIT ?
        )
        ORDER BY id
        ''',
        (*parameters, limit),
    ).fetchall()


def create_user(email, username, password_hash):
    db = get_db()
    cursor = db.execute(
        'INSERT INTO users (email, username, password_hash) VALUES (?, ?, ?)',
        (email, username, password_hash),
    )
    db.commit()
    return cursor.lastrowid


def get_user_by_email(email):
    return get_db().execute(
        'SELECT * FROM users WHERE email = ? COLLATE NOCASE',
        (email,),
    ).fetchone()


def get_user_by_id(user_id):
    return get_db().execute(
        'SELECT id, email, username, created_at FROM users WHERE id = ?',
        (user_id,),
    ).fetchone()


def get_rankings(since=None, limit=10):
    parameters = []
    date_filter = ''
    if since is not None:
        date_filter = 'WHERE throw_results.created_at >= ?'
        parameters.append(since)

    parameters.append(limit)
    return get_db().execute(
        f'''
        SELECT
            users.id AS user_id,
            users.username,
            COUNT(throw_results.id) * 3 AS total_throws,
            SUM(throw_results.success_count) AS successes,
            ROUND(
                SUM(throw_results.success_count) * 100.0
                / (COUNT(throw_results.id) * 3),
                1
            ) AS success_rate
        FROM users
        JOIN user_results ON user_results.user_id = users.id
        JOIN throw_results ON throw_results.id = user_results.result_id
        {date_filter}
        GROUP BY users.id, users.username
        ORDER BY success_rate DESC, total_throws DESC, users.id
        LIMIT ?
        ''',
        parameters,
    ).fetchall()


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

    with app.app_context():
        ensure_schema()
