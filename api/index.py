from datetime import datetime
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
        
        # 1. Fetch Menu (Changed from 'Inventory' to match our setup)
        menu_sheet = sheet.worksheet("Menu")
        items = menu_sheet.get_all_records()
        
        # Only show items marked as 'Active'
        visible_items = [i for i in items if i.get('Status') == 'Active']
        
        # 2. Fetch Settings for 'The Nudge' (Bake Day, etc.)
        try:
            settings_sheet = sheet.worksheet("Settings")
            settings_data = settings_sheet.get_all_records()
            details = {item['Setting Name']: item['Value'] for item in settings_data if item.get('Setting Name')}
        except:
            # Fallback if Settings tab is missing or formatted wrong
            details = {'Next Bake Date': 'TBD'}

        return render_template('index.html', items=visible_items, details=details)

    except Exception as e:
        print(f"BAKERY_ERROR: {e}")
        # DEFENSIVE: Instead of a text error, we show the page with empty data
        # so the customer never sees a 'Broken' site.
        return render_template('index.html', items=[], details={'Next Bake Date': 'Updating Soon'})

@app.route('/submit', methods=['POST'])
def submit():
    try:
        # 1. Capture Form Data
        name = request.form.get('name')
        phone = request.form.get('contact')
        bread = request.form.get('bread')
        notes = request.form.get('notes')
        
        # 2. Generate Real-Time Timestamp
        timestamp = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
        
       # 3. Log Order
        sheet = get_sheet()
        order_sheet = sheet.worksheet("Orders")
        
        # We add 'value_input_option' to remove that apostrophe
        order_sheet.append_row(
            [timestamp, name, phone, bread, notes, 'New'], 
            value_input_option='USER_ENTERED'
        )
        
        # 4. Fetch Details for Success Page
        settings_sheet = sheet.worksheet("Settings")
        settings = settings_sheet.get_all_records()
        details = {item['Setting Name']: item['Value'] for item in settings}
        
        return render_template('success.html', name=name, details=details)
    
    except Exception as e:
        print(f"Error submitting order: {e}")
        return "There was an issue processing your reservation. Please try again or contact us directly."
