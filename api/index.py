from datetime import datetime, timedelta
import os
import json
import urllib.request
from flask import Flask, render_template, request, redirect, url_for
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__, template_folder='../templates')

def get_sheet():
    info = json.loads(os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON'))
    scope = ['https://www.googleapis.com/auth/spreadsheets']
    creds = Credentials.from_service_account_info(info, scopes=scope)
    client = gspread.authorize(creds)
    return client.open_by_key(os.environ.get('GOOGLE_SHEET_ID'))

def get_bake_settings():
    try:
        sheet = get_sheet()
        settings_sheet = sheet.worksheet("Settings")
        data = settings_sheet.get_all_records()
        details = {item['Setting Name']: item['Value'] for item in data if item.get('Setting Name')}
        
        bake_date_str = details.get('Next Bake Date', '01/01/2099')
        bake_date_dt = None
        
        formats = ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"]
        for fmt in formats:
            try:
                bake_date_dt = datetime.strptime(bake_date_str, fmt)
                break
            except ValueError:
                continue
        
        if not bake_date_dt:
            bake_date_dt = datetime.now() + timedelta(days=7)

        deadline_dt = bake_date_dt - timedelta(days=1)
        deadline_dt = deadline_dt.replace(hour=23, minute=59)
        
        return bake_date_dt, deadline_dt, deadline_dt.strftime("%A, %B %d at 11:59 PM")
    except Exception as e:
        print(f"Settings Error: {e}")
        future = datetime.now() + timedelta(days=1)
        return future, future, "the night before bake day"

def send_bakery_email(subject, recipient, name=None):
    try:
        _, _, deadline_text = get_bake_settings()
        unsubscribe_url = f"https://aiarabakery.com/unsubscribe?email={recipient}"
        
        html_content = f"""
            <html>
                <body style="font-family: sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 8px;">
                        <h2 style="color: #d4a373;">Hello{"" if not name else " " + name}!</h2>
                        <p>Our organic sourdough menu is now live. We’ve got fresh flour from our farm partners in Virginia.</p>
                        <p>Orders are open until <strong>{deadline_text}</strong>.</p>
                        <div style="text-align: center; margin: 20px 0;">
                            <a href="https://aiarabakery.com" style="background-color: #d4a373; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px;">View Menu & Order</a>
                        </div>
                    </div>
                </body>
            </html>
        """
        
        url = "https://api.brevo.com/v3/smtp/email"
        api_key = os.environ.get('BREVO_API_KEY')
        
        data = {
            "sender": {"name": "Aiara Bakery", "email": "greg@aiarabakery.com"},
            "to": [{"email": recipient}],
            "subject": subject,
            "htmlContent": html_content
        }
        
        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), method='POST')
        req.add_header('api-key', api_key)
        req.add_header('Content-Type', 'application/json')
        req.add_header('Accept', 'application/json')
        
        with urllib.request.urlopen(req) as response:
            print(f"Email sent: {response.status}")
            
    except Exception as e:
        print(f"Brevo API Error: {e}")

@app.route('/')
def home():
    try:
        sheet = get_sheet()
        items = sheet.worksheet("Menu").get_all_records()
        visible_items = [i for i in items if i.get('Status') == 'Active']
        
        # FIX 1: Corrected indentation here!
        settings = {i['Setting Name']: i['Value'] for i in sheet.worksheet("Settings").get_all_records() if i.get('Setting Name')}
        
        if settings.get('Pickup Windows'):
            settings['window_list'] = [w.strip() for w in settings['Pickup Windows'].split(',')]
            
        # Pull the DC windows from the Google Sheet
        if settings.get('DC Pickup Windows'):
            settings['dc_window_list'] = [w.strip() for w in settings['DC Pickup Windows'].split(',')]
            
        return render_template('index.html', items=visible_items, details=settings)
    except Exception as e:
        return render_template('index.html', items=[], details={'Store Status': 'Open'})

@app.route('/submit', methods=['POST'])
def submit():
    try:
        name = request.form.get('name')
        contact = request.form.get('contact').strip().lower()
        order_summary = request.form.get('order_summary')
        timestamp = datetime.now()
        
        _, deadline_dt, deadline_text = get_bake_settings()
