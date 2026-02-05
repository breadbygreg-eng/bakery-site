from flask import Flask, render_template, request

app = Flask(__name__, template_folder='../templates')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    name = request.form.get('name')
    bread = request.form.get('bread')
    return f"<h1>Order Received!</h1><p>Thanks {name}, we'll contact you about your {bread} loaf soon!</p>"

# DO NOT add a 'def handler' here. 
# Vercel's Python runtime will find the 'app' object automatically 
# if the vercel.json is set up as a simple rewrite.
