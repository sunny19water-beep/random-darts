from .app import draw_number
from .app import draw_Advanced_numbers
from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/next')
def next_page():
    random_number = draw_number()
    return render_template('second.html', random_number=random_number)

@app.route('/Advanced')
def advanced_page():
    random_number, bed_number = draw_Advanced_numbers()
    return render_template('Advanced.html', random_number=random_number, bed_number=bed_number)


if __name__ == '__main__':
    app.run()