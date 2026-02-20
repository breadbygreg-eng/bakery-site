from datetime import datetime, timedelta
import os
import json
from flask import Flask, render_template, request, redirect, url_for
import gspread
from google.oauth2.service_account import Credentials

# --- Modern Brevo Imports ---
import brevo_python
from brevo_python.rest import ApiException

app = Flask(__name__, template_folder='../templates')

# --- Helper: Google Sheets Connection ---
def get_sheet():
    info = json.loads(os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON'))
    scope = ['https://www.googleapis.com/auth/spreadsheets']
    creds = Credentials.from_service_account_info(info, scopes=scope)
    client = gspread.authorize(creds)
    return client.open_by_key(os.environ.get('GOOGLE_SHEET_ID'))

def get_deadline():
    """Calculates midnight of the day before the Next Bake Date from Settings."""
    try:
        sheet = get_sheet()
        settings_sheet = sheet.worksheet("Settings")
        settings_data = settings_sheet.get_all_records()
        
        details = {item['Setting Name']: item['Value'] for item in settings_data if item.get('Setting Name')}
        bake_date_str = details.get('Next Bake Date')
        
        # Expects MM/DD/YYYY format in your Google Sheet
        bake_date = datetime.strptime(bake_date_str, "%m/%d/%Y")
        
        # Calculate midnight (11:59 PM) of the day before
        deadline_date = bake_date - timedelta(days=1)
        return deadline_date.strftime("%A, %B %d at 11:59 PM")
    except Exception as e:
        print(f"Deadline calculation error: {e}")
        return "the night before bake day"

# --- Professional Brevo Email Function ---
def send_bakery_email(subject, recipient, name=None):
    configuration = brevo_python.Configuration()
    configuration.api_key['api-key'] = os.environ.get('BREVO_API_KEY')
    
    api_instance = brevo_python.TransactionalEmailsApi(brevo_python.ApiClient(configuration))
    
    deadline = get_deadline()
    unsubscribe_url = f"https://aiarabakery.com/unsubscribe?email={recipient}"
    
    # Updated Email Content with your farm partner copy and dynamic deadline
    html_content = f"""
        <html>
            <body style="font-family: sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 8px;">
                    <h2 style="color: #d4a373;">Hello{"" if not name else " " + name}!</h2>
                    <p>Our organic sourdough menu is now live for this week’s bake. We’ve got fresh flour from our farm partners in Virginia, and the loaves look better than ever.</p>
                    
                    <p><strong>On the Bench this week:</strong></p>
                    <ul>
                        <li><strong>100% Whole Wheat</strong> (650g & 1kg) <em>(Our favorite)</em></li>
                        <li><strong>Country Bread</strong> (650g & 1kg)</li>
                        <li><strong>Cashew & Raisin</strong></li>
                    </ul>
                    
                    <p>Orders are open until <strong>{deadline}</strong>. Click below to reserve your loaves:</p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="https://aiarabakery.com" style="background-color: #d4a373; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">View Menu & Order</a>
                    </div>
                    
                    <hr style="border: none; border-top: 1px solid #eee;">
                    <small style="color: #888;">
                        Sent from Aiara Bakery. <a href="{unsubscribe_url}" style="color: #d4a373;">Unsubscribe</a>.
                    </small>
                </div>
            </body>
        </html>
    """

    send_email = brevo_python.SendSmtpEmail(
        to=[{"email": recipient}],
        sender={"name": "Aiara Bakery", "email": "greg@aiarabakery.com"},
        subject=subject,
        html_content=html_content
    )

    try:
        api_instance.send_trans_email(send_email)
    except ApiException as e:
        print(f"Brevo API Error: {e}")

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
        print(f"HOME_PAGE_ERROR: {e}")
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

        if join_list:
            sub_sheet = sheet.worksheet("Subscribers")
            try:
                sub_sheet.find(contact)
            except gspread.exceptions.CellNotFound:
                sub_sheet.append_row([timestamp.strftime("%m/%d/%Y %H:%M:%S"), contact, 'Active'], value_input_option='USER_ENTERED')
                send_bakery_email("🍞 You're on the Bake List!", contact, name)

        return render_template('success.html', name=name)
    except Exception as e:
        print(f"SUBMISSION_ERROR: {e}")
        return f"Submission error: {e}"

@app.route('/unsubscribe')
def unsubscribe():
    email = request.args.get('email')
    if not email:
        return "<h3>Error</h3><p>No email provided.</p>"
    
    try:
        sheet = get_sheet()
        sub_sheet = sheet.worksheet("Subscribers")
        cell = sub_sheet.find(email.strip().lower())
        sub_sheet.update_cell(cell.row, 3, 'Unsubscribed')
        return f"<h3>Success</h3><p>{email} has been unsubscribed from our weekly menu distribution.</p>"
    except gspread.exceptions.CellNotFound:
        return "<h3>Not Found</h3><p>This email is not on our active list.</p>"
    except Exception as e:
        print(f"UNSUBSCRIBE_ERROR: {e}")
        return "<h3>Error</h3><p>An error occurred. Please contact us directly.</p>"

@app.route('/submit', methods=['POST'])
def submit():
    try:
        # ... (all your existing form gathering logic here) ...
        
        timestamp = datetime.now()
        sheet = get_sheet()
        
        # Calculate the deadline
        deadline_str = get_deadline() # e.g., "Friday, February 20 at 11:59 PM"
        # We also need the raw datetime object to compare
        settings_sheet = sheet.worksheet("Settings")
        bake_date_str = {i['Setting Name']: i['Value'] for i in settings_sheet.get_all_records()}['Next Bake Date']
        bake_deadline_dt = datetime.strptime(bake_date_str, "%m/%d/%Y") - timedelta(days=1)
        bake_deadline_dt = bake_deadline_dt.replace(hour=23, minute=59, second=59)

        # 1. Always Save the Order First
        order_sheet = sheet.worksheet("Orders")
        order_sheet.append_row(
            [timestamp.strftime("%m/%d/%Y %H:%M:%S"), name, contact, order_summary, logistics, f"{pickup_window} {other_location}", subscription_type, notes], 
            value_input_option='USER_ENTERED'
        )

        # 2. Determine the Response Message
        is_late = timestamp > bake_deadline_dt
        
        if is_late:
            title = "Order Received (Late)"
            msg = f"Thanks, {name}! Your order came in after our {deadline_str} cutoff. We'll do our best to fit it in, but please keep an eye out for a confirmation email regarding which bake day you're scheduled for."
        else:
            title = "Order Confirmed!"
            msg = f"Thanks, {name}! Your order is in for our next bake day. We'll see you at the pickup window!"

        # 3. Handle Subscription & Email
        if join_list:
            # ... (your existing sub_sheet.append_row logic) ...
            send_bakery_email("🍞 You're on the Bake List!", contact, name)

        return render_template('success.html', name=name, message=msg, title=title)
        
    except Exception as e:
        print(f"SUBMISSION_ERROR: {e}")
        return f"Submission error: {e}"
