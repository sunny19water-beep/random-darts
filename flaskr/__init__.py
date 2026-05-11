from .app import draw_number
from .app import draw_Advanced_numbers
from flask import Flask, render_template,url_for,redirect,request
# from flask_sqlalchemy import SQLAlchemy
from datetime import datetime



app = Flask(__name__)



# DB
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///darts.db'
# db = SQLAlchemy(app)

# class Result(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     user_id = db.Column(db.Integer)
#     target = db.Column(db.Integer)
#     result = db.Column(db.Integer)
#     created_at = db.Column(db.DateTime, default=datetime.utcnow)

#成功・失敗判定のform   
# @app.route('/success', methods=['POST'])
# def success():
#     new = Result(user_id=1, target=20, result=1)
#     db.session.add(new)
#     db.session.commit()
#     return redirect(url_for('index'))

# @app.route('/fail', methods=['POST'])
# def fail():
#     new = Result(user_id=1, target=20, result=0)
#     db.session.add(new)
#     db.session.commit()
#     return redirect(url_for('index'))


# 来訪ページ
@app.route('/')
def index():
    # success = Result.query.filter_by(result=1).count()
    # fail = Result.query.filter_by(result=0).count()
    # total = success + fail
    # rate = success / total * 100 if total > 0 else 0
    rate=0 #仮の値
    return render_template('index.html', rate=rate)

# ノーマル
@app.route('/next')
def next_page():
    random_number = draw_number()
    return render_template('second.html', random_number=random_number)

@app.route('/success',methods=['POST'])
def success():
    count=request.form.get('count')
    return redirect(url_for('next_page'))

# アドバンス
@app.route('/Advanced')
def advanced_page():
    random_number, bed_number = draw_Advanced_numbers()
    return render_template('Advanced.html', random_number=random_number, bed_number=bed_number)

@app.route('/Advanced_success',methods=['POST'])
def Advanced_success():
    count=request.form.get('count')
    return redirect(url_for('advanced_page'))


if __name__ == '__main__':
    with app.app_context():
        # db.create_all()
        app.run()


# 下は実行コマンド
# flask --app flaskr run