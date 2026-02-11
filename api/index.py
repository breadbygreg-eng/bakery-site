from datetime import datetime
import os
import json
import smtplib
from email.mime.text import MIMEText
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

# --- NEW: Automated Email Function ---
def send_admin_alert(order_data):
    sender = "breadbygreg@gmail.com"
    # This pulls your App Password from Vercel Environment Variables
    pw = os.environ.get('GMAIL_APP_PASSWORD') 
    
    subject = f"🍞 New Aiara Order: {order_data['name']}"
    body = f"Item: {order_data['bread']}\nNotes: {order_data['notes']}\nContact: {order_data['contact']}"
    
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = sender

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, pw)
            server.sendmail(sender, sender, msg.as_string())
    except Exception as e:
        print(f"Email Alert Failed: {e}")

@app.route('/')
def home():
    try:
        sheet = get_sheet()
        menu_sheet = sheet.worksheet("Menu")
        items = menu_sheet.get_all_records()
        visible_items = [i for i in items if i.get('Status') == 'Active']
        
        try:
            settings_sheet = sheet.worksheet("Settings")
            settings_data = settings_sheet.get_all_records()
            details = {item['Setting Name']: item['Value'] for item in settings_data if item.get('Setting Name')}
        except:
            details = {'Next Bake Date': 'TBD'}

        return render_template('index.html', items=visible_items, details=details)
    except Exception as e:
        print(f"BAKERY_ERROR: {e}")
        return render_template('index.html', items=[], details={'Next Bake Date': 'Updating Soon'})

@app.route('/submit', methods=['POST'])
def submit():
    try:
        name = request.form.get('name')
        phone = request.form.get('contact')
        bread = request.form.get('bread')
        notes = request.form.get('notes')
        timestamp = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
        
        sheet = get_sheet()
        order_sheet = sheet.worksheet("Orders")
        order_sheet.append_row(
            [timestamp, name, phone, bread, notes, 'New'], 
            value_input_option='USER_ENTERED'
        )
        
        # --- NEW: Trigger the Email Alert ---
        send_admin_alert({'name': name, 'bread': bread, 'notes': notes, 'contact': phone})
        
        settings_sheet = sheet.worksheet("Settings")
        settings = settings_sheet.get_all_records()
        details = {item['Setting Name']: item['Value'] for item in settings}
        
        return render_template('success.html', name=name, details=details)
    except Exception as e:
        print(f"Error submitting order: {e}")
        return "There was an issue processing your reservation."

# --- NEW: Route to handle 'Notify Me' Signups ---
@app.route('/subscribe', methods=['POST'])
def subscribe():
    try:
        contact = request.form.get('sub_contact')
        timestamp = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
        
        sheet = get_sheet()
        sub_sheet = sheet.worksheet("Subscribers")
        sub_sheet.append_row([timestamp, contact], value_input_option='USER_ENTERED')
        
        return "<h3>Success! You're on the list.</h3><p>We'll notify you when the oven is hot.</p><a href='/'>Back to Menu</a>"
    except Exception as e:
        print(f"Subscription Error: {e}")
        return "Could not add to list. Please try again later."
