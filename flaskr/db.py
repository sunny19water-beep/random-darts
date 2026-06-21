import sqlite3

import click
from flask import current_app, g


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row

    return g.db


def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def ensure_schema():
    db = get_db()
    with current_app.open_resource('schema.sql') as schema_file:
        db.executescript(schema_file.read().decode('utf-8'))
    db.commit()


def init_db():
    db = get_db()
    db.execute('DROP TABLE IF EXISTS throw_results')
    ensure_schema()


@click.command('init-db')
def init_db_command():
    """結果データを消去し、データベースを初期化する。"""
    init_db()
    click.echo('Initialized the database.')


def save_result(number, success_count, mode, bed=None, user_id=None):
    db = get_db()
    db.execute(
        '''
        INSERT INTO throw_results
            (user_id, number, success_count, mode, bed)
        VALUES (?, ?, ?, ?, ?)
        ''',
        (user_id, str(number), success_count, mode, bed),
    )
    db.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

    with app.app_context():
        ensure_schema()
