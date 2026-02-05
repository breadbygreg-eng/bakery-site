from flask import Flask, render_template, request

# The '../templates' is crucial so it finds your HTML folder
app = Flask(__name__, template_folder='../templates')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    # This captures the order data from your form
    name = request.form.get('name')
    bread = request.form.get('bread')
    notes = request.form.get('notes')
    
    # For now, it just shows a "Thank You" message
    return f"<h1>Order Received!</h1><p>Thanks {name}, we'll contact you about your {bread} loaf soon!</p><a href='/'>Back to Home</a>"

# Vercel needs this exact function to bridge the gap
def handler(event, context):
    return app(event, context)
