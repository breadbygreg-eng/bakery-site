import os
import json
from flask import Flask, render_template, request
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__, template_folder='../templates')

def get_sheet():
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
        # This gets all data including your math columns
        items = inventory_sheet.get_all_records()
        
        # We only show items marked as 'Active'
        visible_items = [i for i in items if i.get('Status') == 'Active']
        return render_template('index.html', items=visible_items)
    except Exception as e:
        # This will show you exactly what's wrong in the Vercel Logs
        print(f"BAKERY_ERROR: {e}")
        return "The bakery is currently updating. Please check back in a few minutes!"

@app.route('/submit', methods=['POST'])
def submit():
    try:
        # 1. Capture Form Data
        name = request.form.get('name')
        phone = request.form.get('phone')
        bread = request.form.get('bread')
        notes = request.form.get('notes')
        
        # 2. Log Order to Google Sheets
        sheet = get_sheet()
        order_sheet = sheet.worksheet("Orders")
        order_sheet.append_row([name, phone, bread, notes, 'New'])
        
        # 3. Fetch Pickup Details from 'Settings' tab
        settings_sheet = sheet.worksheet("Settings")
        settings = settings_sheet.get_all_records()
        
        # Convert list of dicts to a simple dictionary for easy access
        # This turns it into: {'Pickup Instructions': 'Thursday...', 'Delivery Info': 'Friday...'}
        details = {item['Setting Name']: item['Value'] for item in settings}
        
        return render_template('success.html', name=name, details=details)
        
    except Exception as e:
        print(f"SUBMIT_ERROR: {e}")
        return "Order logged, but there was a glitch showing the confirmation. Don't worry, Greg has your order!"
