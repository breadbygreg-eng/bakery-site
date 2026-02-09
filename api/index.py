from flask import Flask, render_template, request
import json
import os

app = Flask(__name__, template_folder='../templates')

def get_menu():
    # This opens your menu.json file and reads the data
    with open(os.path.join(os.path.dirname(__file__), '../menu.json'), 'r') as f:
        return json.load(f)

@app.route('/')
def home():
    menu_data = get_menu()
    return render_template('index.html', menu=menu_data)

@app.route('/submit', methods=['POST'])
def submit():
    # This is where we will eventually save orders to a spreadsheet
    name = request.form.get('name')
    return f"<h1>Thanks {name}!</h1><p>Order received. Check your phone for confirmation soon.</p>"
