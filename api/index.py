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
        visible_items = [i for i in items if i.get('Status') == 'Active']
        
        try:
            settings_sheet = sheet.worksheet("Settings")
            settings_data = settings_sheet.get_all_records()
            details = {item['Setting Name']: item['Value'] for item in settings_data if item.get('Setting Name')}
            
            # Convert 'Pickup Windows' string to a list for the dropdown
            if details.get('Pickup Windows'):
                details['window_list'] = [w.strip() for w in details['Pickup Windows'].split(',')]
            else:
                details['window_list'] = []
                
        except:
            details = {'Next Bake Date': 'TBD', 'Store Status': 'Open', 'window_list': []}

        return render_template('index.html', items=visible_items, details=details)
    except Exception as e:
        print(f"BAKERY_ERROR: {e}")
        return render_template('index.html', items=[], details={'Next Bake Date': 'Updating Soon', 'Store Status': 'Open'})

@app.route('/submit', methods=['POST'])
def submit():
    try:
        # 1. Capture Form Data
        name = request.form.get('name')
        contact = request.form.get('contact')
        logistics = request.form.get('logistics')
        pickup_window = request.form.get('pickup_window', 'N/A')
        other_location = request.form.get('other_location', '')
        subscription = "Yes" if request.form.get('subscription') else "No"
        order_summary = request.form.get('order_summary') # "2x Country, 1x WW"
        notes = request.form.get('notes')
        timestamp = datetime.now().strftime("%m/%d/%Y %H:%M:%S")

        # 2. Log Order to Google Sheets
        sheet = get_sheet()
        order_sheet = sheet.worksheet("Orders")
        # Column Order: Timestamp, Name, Contact, Order, Logistics, Details, Subscription, Notes
        order_sheet.append_row(
            [timestamp, name, contact, order_summary, logistics, f"{pickup_window} {other_location}", subscription, notes], 
            value_input_option='USER_ENTERED'
        )
        
        # 3. Enhanced Admin Alert
        admin_body = (f"🍞 NEW ORDER: {name}\n"
                      f"Items: {order_summary}\n"
                      f"Logistics: {logistics} ({pickup_window}{other_location})\n"
                      f"Subscription: {subscription}\n"
                      f"Notes: {notes}")
        send_email(f"Aiara Order: {name}", admin_body, "breadbygreg@gmail.com")
        
        return render_template('success.html', name=name, details={'Pickup Instructions': 'See your logistics choice for details.'})
    except Exception as e:
        print(f"Error: {e}")
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
            welcome_body = "Welcome to Aiara Bakery!\n\nYou'll be the first to know when our sourdough oven is preheated.\n\nTo stop receiving these, visit: aiarabakery.com/unsubscribe"
            send_email("🍞 You're on the Aiara Bake List!", welcome_body, contact)
        
        return "<h3>You're on the list!</h3><p>We'll notify you when the next bake begins.</p><a href='/'>Back to Menu</a>"
    except Exception as e:
        print(f"Subscription Error: {e}")
        return "Could not add to list. Please try again later."

@app.route('/unsubscribe', methods=['GET', 'POST'])
def unsubscribe():
    if request.method == 'POST':
        contact = request.form.get('contact')
        try:
            sheet = get_sheet()
            sub_sheet = sheet.worksheet("Subscribers")
            cell = sub_sheet.find(contact)
            sub_sheet.update_cell(cell.row, 3, 'Unsubscribed')
            return "<h3>You have been unsubscribed.</h3><p>We're sorry to see you go!</p>"
        except:
            return "Contact not found on our list."
    return render_template('unsubscribe.html')
