from flask import Flask, render_template, request

app = Flask(__name__, template_folder='../templates')

# Your Weekly Menu - Update this whenever you like!
MENU = [
    {"id": 1, "name": "Country Sourdough", "price": 10.00},
    {"id": 2, "name": "Jalapeño Cheddar", "price": 12.00},
    {"id": 3, "name": "Rosemary Sea Salt", "price": 11.00}
]

@app.route('/')
def index():
    return render_template('index.html', items=MENU)

@app.route('/order', methods=['POST'])
def order():
    name = request.form.get('name')
    bread = request.form.get('bread_name')
    # This will show a simple success message to the customer
    return f"<h1>Thanks, {name}!</h1><p>We've received your order for {bread}. We'll contact you for payment soon.</p>"

# Required for Vercel to treat this as a serverless function
def handler(event, context):
    return app(event, context)