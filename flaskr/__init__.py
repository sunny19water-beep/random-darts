from flask import Flask, redirect, render_template, url_for

from .app import draw_Advanced_numbers, draw_number

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/next')
def next_page():
    random_number = draw_number()
    return render_template('second.html', random_number=random_number)

@app.post('/success')
def success():
    return redirect(url_for('next_page'))

@app.route('/Advanced')
@app.route('/advanced')
def advanced_page():
    random_number, bed_number = draw_Advanced_numbers()
    return render_template('Advanced.html', random_number=random_number, bed_number=bed_number)

@app.post('/Advanced_success')
@app.post('/advanced/success')
def advanced_success():
    return redirect(url_for('advanced_page'))
