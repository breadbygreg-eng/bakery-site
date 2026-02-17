from datetime import datetime
import os
import json
import smtplib
from email.mime.text import MIMEText
from flask import Flask, render_template, request, redirect, url_for
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

# --- Helper: Email Notifications with Unsubscribe Link ---
def send_bakery_email(subject, body, recipient):
    sender = "breadbygreg@gmail.com"
    pw = os.environ.get('GMAIL_APP_PASSWORD')
    
    # Adding the compliant footer to every email
    unsubscribe_url = f"https://aiarabakery.com/unsubscribe?email={recipient}"
    footer = f"\n\n---\nYou are receiving this because you signed up at AiaraBakery.com.\nTo stop receiving these emails, click here: {unsubscribe_url}"
    
    msg = MIMEText(body + footer)
    msg['Subject'] = subject
    msg['From'] = f"Aiara Bakery <{sender}>"
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
        
        settings_sheet = sheet.worksheet("Settings")
        settings_data = settings_sheet.get_all_records()
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
        contact = request.form.get('contact').strip().lower()
        logistics = request.form.get('logistics')
        pickup_window = request.form.get('pickup_window', 'N/A')
        other_location = request.form.get('other_location', '')
        subscription_type = "Yes" if request.form.get('subscription') else "No"
        join_list = request.form.get('join_list') 
        order_summary = request.form.get('order_summary')
        notes = request.form.get('notes')
        timestamp = datetime.now()

        sheet = get_sheet()
        order_sheet = sheet.worksheet("Orders")
        order_sheet.append_row(
            [timestamp.strftime("%m/%d/%Y %H:%M:%S"), name, contact, order_summary, logistics, f"{pickup_window} {other_location}", subscription_type, notes], 
            value_input_option='USER_ENTERED'
        )

        # Handle deduplicated subscription
        if join_list:
            sub_sheet = sheet.worksheet("Subscribers")
            try:
                sub_sheet.find(contact)
            except gspread.exceptions.CellNotFound:
                sub_sheet.append_row([timestamp.strftime("%m/%d/%Y %H:%M:%S"), contact, 'Active'], value_input_option='USER_ENTERED')
                welcome_body = "Welcome to the Aiara Bakery weekly menu distribution! Every week, you'll be the first to know what's coming out of our Tom Chandley oven."
                send_bakery_email("🍞 You're on the Bake List!", welcome_body, contact)

        return render_template('success.html', name=name)
    except Exception as e:
        print(f"Submission error: {e}")
        return "Submission error."

@app.route('/unsubscribe')
def unsubscribe():
    email = request.args.get('email')
    if not email:
        return "<h3>Error</h3><p>No email provided.</p>"
    
    try:
        sheet = get_sheet()
        sub_sheet = sheet.worksheet("Subscribers")
        cell = sub_sheet.find(email.strip().lower())
        
        # Updates the Status column (Column 3) to 'Unsubscribed'
        sub_sheet.update_cell(cell.row, 3, 'Unsubscribed')
        return f"<h3>Success</h3><p>{email} has been unsubscribed from our weekly menu distribution.</p>"
    except gspread.exceptions.CellNotFound:
        return "<h3>Not Found</h3><p>This email is not on our active list.</p>"
    except Exception as e:
        print(f"Unsubscribe Error: {e}")
        return "<h3>Error</h3><p>An error occurred. Please contact us directly.</p>"

@app.route('/subscribe', methods=['POST'])
def subscribe():
    try:
        contact = request.form.get('sub_contact').strip().lower()
        timestamp = datetime.now()
        sheet = get_sheet()
        sub_sheet = sheet.worksheet("Subscribers")
        
        try:
            sub_sheet.find(contact)
            return "<h3>Already on the list!</h3><p>You're all set to receive the next bake notification.</p><a href='/'>Back to Menu</a>"
        except gspread.exceptions.CellNotFound:
            sub_sheet.append_row([timestamp.strftime("%m/%d/%Y %H:%M:%S"), contact, 'Active'], value_input_option='USER_ENTERED')
            welcome_body = "Thanks for joining the Aiara Bakery list! You'll receive our organic sourdough menu every week."
            send_bakery_email("🍞 You're on the Bake List!", welcome_body, contact)
            return "<h3>Success!</h3><p>You've been added to our distribution list.</p><a href='/'>Back to Menu</a>"
    except Exception as e:
        print(f"Subscription Error: {e}")
        return "Subscription error."
