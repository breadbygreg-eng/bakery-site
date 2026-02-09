import os
import json
from flask import Flask, render_template, request
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__, template_folder='../templates')

def get_sheet():
    # This reads the secret key you just pasted into Vercel
    info = json.loads(os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON'))
    scope = ['https://www.googleapis.com/auth/spreadsheets']
    creds = Credentials.from_service_account_info(info, scopes=scope)
    client = gspread.authorize(creds)
    return client.open_by_key(os.environ.get('GOOGLE_SHEET_ID'))

@app.route('/')
def home():
    try:
        sheet = get_sheet()
        inventory_sheet = sheet.worksheet("Inventory")
        items = inventory_sheet.get_all_records()
        
        # Only show items where Status is 'Active'
        visible_items = [i for i in items if i.get('Status') == 'Active']
        return render_template('index.html', items=visible_items)
    except Exception as e:
        print(f"Error: {e}")
        return "The bakery is currently updating. Please check back in a few minutes!"

@app.route('/submit', methods=['POST'])
def submit():
    name = request.form.get('name')
    phone = request.form.get('phone')
    bread = request.form.get('bread')
    notes = request.form.get('notes')
    
    # This adds the order as a new row in your 'Orders' tab
    sheet = get_sheet()
    order_sheet = sheet.worksheet("Orders")
    order_sheet.append_row([name, phone, bread, notes, 'Unpaid'])
    
    return f"<h1>Order Received!</h1><p>Thanks {name}, your {bread} is on the list!</p><a href='/'>Back to Home</a>"
