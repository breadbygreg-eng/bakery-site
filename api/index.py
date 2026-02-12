from datetime import datetime
import os
import json
import smtplib
from email.mime.text import MIMEText
from flask import Flask, render_template, request
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__, template_folder='../templates')

# --- Helper: Google Sheets Connection ---
def get_sheet():
    info = json.loads(os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON'))
    scope = ['https://www.googleapis.com/auth/spreadsheets']
    creds = Credentials.from_service_account_info(info, scopes=scope)
    client = gspread.authorize(creds)
    return client.open_by_key(os.environ.get('GOOGLE_SHEET_ID'))

# --- Helper: Email Notifications ---
def send_email(subject, body, recipient):
    sender = "breadbygreg@gmail.com"
    pw = os.environ.get('GMAIL_APP_PASSWORD')
    
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, pw)
            server.sendmail(sender, recipient, msg.as_string())
    except Exception as e:
        print(f"Email Error: {e}")

# --- Routes ---

@app.route('/')
def home():
    try:
        sheet = get_sheet()
        menu_sheet = sheet.worksheet("Menu")
        items = menu_sheet.get_all_records()
        
        # Filter for 'Active' status (Case Sensitive)
        visible_items = [i for i in items if i.get('Status') == 'Active']
        
        settings_sheet = sheet.worksheet("Settings")
        settings_data = settings_sheet.get_all_records()
        # Filter empty rows to prevent crashes
        details = {item['Setting Name']: item['Value'] for item in settings_data if item.get('Setting Name')}
        
        if details.get('Pickup Windows'):
            details['window_list'] = [w.strip() for w in details['Pickup Windows'].split(',')]
        
        return render_template('index.html', items=visible_items, details=details)

    except Exception as e:
        print(f"BAKERY_ERROR: {e}")
        return render_template('index.html', items=[], details={'Next Bake Date': 'Updating Soon', 'Store Status': 'Open'})

@app.route('/submit', methods=['POST'])
def submit():
    try:
        name = request.form.get('name')
        contact = request.form.get('contact')
        logistics = request.form.get('logistics')
        pickup_window = request.form.get('pickup_window', 'N/A')
        other_location = request.form.get('other_location', '')
        subscription = "Yes" if request.form.get('subscription') else "No"
        order_summary = request.form.get('order_summary')
        notes = request.form.get('notes')
        timestamp = datetime.now()

        sheet = get_sheet()
        order_sheet = sheet.worksheet("Orders")
        # Column Order: Timestamp, Name, Contact, Order, Logistics, Details, Subscription, Notes
        order_sheet.append_row(
            [timestamp.strftime("%m/%d/%Y %H:%M:%S"), name, contact, order_summary, logistics, f"{pickup_window} {other_location}", subscription, notes], 
            value_input_option='USER_ENTERED'
        )

        settings_sheet = sheet.worksheet("Settings")
        settings = settings_sheet.get_all_records()
        details = {item['Setting Name']: item['Value'] for item in settings if item.get('Setting Name')}

        # Late Order logic
        is_late = False
        try:
            bake_date = datetime.strptime(details.get('Next Bake Date'), "%m/%d/%Y")
            if timestamp > bake_date:
                is_late = True
        except:
            pass

        admin_body = f"🍞 NEW ORDER: {name}\nItems: {order_summary}\nLogistics: {logistics}\nLate: {is_late}"
        send_email(f"Aiara Order: {name}", admin_body, "breadbygreg@gmail.com")
        
        return render_template('success.html', name=name, details=details, is_late=is_late)
    except Exception as e:
        print(f"Submission error: {e}")
        return "Submission error."

@app.route('/subscribe', methods=['POST'])
def subscribe():
    try:
        contact = request.form.get('sub_contact')
        timestamp = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
        sheet = get_sheet()
        sub_sheet = sheet.worksheet("Subscribers")
        sub_sheet.append_row([timestamp, contact, 'Active'], value_input_option='USER_ENTERED')
        
        if "@" in contact:
            welcome_body = "Welcome to Aiara Bakery!\n\nYou'll be the first to know when the oven is preheated."
            send_email("🍞 You're on the Aiara Bake List!", welcome_body, contact)
        
        return "<h3>Success!</h3><p>You're on the list.</p><a href='/'>Back to Menu</a>"
    except Exception as e:
        print(f"Subscription Error: {e}")
        return "Subscription error."
