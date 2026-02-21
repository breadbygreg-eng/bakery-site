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
        
        settings_dict = {}
        for item in data:
            if item.get('Setting Name'):
                settings_dict[item['Setting Name']] = item['Value']
        
        bake_date_str = settings_dict.get('Next Bake Date', '01/01/2099')
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

def send_bakery_email(subject, recipient, name=None, total="0.00"):
    try:
        _, _, deadline_text = get_bake_settings()
        unsubscribe_url = f"https://aiarabakery.com/unsubscribe?email={recipient}"
        
        html_content = f"""
            <html>
                <body style="font-family: sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 8px;">
                        <h2 style="color: #d4a373;">Hello{"" if not name else " " + name}!</h2>
                        <p>We've received your order and added it to the bake list. Thank you for supporting Aiara Bakery!</p>
                        
                        <div style="background: #f9f9f9; padding: 20px; border-left: 4px solid #008CFF; margin: 25px 0;">
                            <h3 style="margin-top: 0; color: #333;">Payment Instructions</h3>
                            <p>Your total for this bake is <strong>${total}</strong>. To finalize your order, please send your payment via Venmo to <strong>@aiarabakery</strong>.</p>
                            <a href="https://venmo.com/aiarabakery" style="display: inline-block; background: #008CFF; color: white; padding: 12px 25px; text-decoration: none; border-radius: 4px; font-weight: bold; margin-top: 10px;">Pay ${total} with Venmo</a>
                        </div>
                        
                        <p>A quick reminder: orders for the upcoming bake close on <strong>{deadline_text}</strong>.</p>
                        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                        <small style="color: #888;">Aiara Bakery | <a href="{unsubscribe_url}">Unsubscribe</a></small>
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
        
        settings = {}
        for i in sheet.worksheet("Settings").get_all_records():
            if i.get('Setting Name'):
                settings[i['Setting Name']] = i['Value']
        
        if settings.get('Pickup Windows'):
            settings['window_list'] = [w.strip() for w in settings['Pickup Windows'].split(',')]
            
        if settings.get('DC Pickup Windows'):
            settings['dc_window_list'] = [w.strip() for w in settings['DC Pickup Windows'].split(',')]
            
        return render_template('index.html', items=visible_items, details=settings)
    except Exception as e:
        # DIAGNOSTIC FIX: This will print the exact Google Sheets error to your screen instead of crashing
        return f"""
            <div style="padding: 50px; font-family: sans-serif; text-align: center;">
                <h2 style="color: #c53030;">Google Sheets Connection Error</h2>
                <p>The website cannot read the spreadsheet. The exact error is:</p>
                <code style="background: #eee; padding: 10px; display: inline-block; border-radius: 4px;">{e}</code>
            </div>
        """
@app.route('/submit', methods=['POST'])
def submit():
    try:
        name = request.form.get('name')
        contact = request.form.get('contact').strip().lower()
        order_summary = request.form.get('order_summary')
        order_total = request.form.get('order_total', '0.00')
        timestamp = datetime.now()
        
        _, deadline_dt, deadline_text = get_bake_settings()
        is_late = timestamp > deadline_dt

        sheet = get_sheet()
        
        settings = {}
        for i in sheet.worksheet("Settings").get_all_records():
            if i.get('Setting Name'):
                settings[i['Setting Name']] = i['Value']

        loc_details = [
            request.form.get('pickup_window'),
            request.form.get('dc_pickup_window'),
            request.form.get('other_location')
        ]
        logistics_details = " ".join([loc for loc in loc_details if loc]).strip() or "N/A"

        # Note the two new columns added at the end of the append_row list!
        sheet.worksheet("Orders").append_row([
            timestamp.strftime("%m/%d/%Y %H:%M:%S"), name, contact, order_summary, 
            request.form.get('logistics'), logistics_details,
            "Yes" if request.form.get('subscription') else "No", request.form.get('notes'),
            f"${order_total}", "Pending"
        ], value_input_option='USER_ENTERED')

        if request.form.get('join_list'):
            sub_sheet = sheet.worksheet("Subscribers")
            
            try:
                # Safely grab existing emails in column B
                existing_emails = sub_sheet.col_values(2)
            except Exception:
                existing_emails = []
                
            if contact not in existing_emails:
                sub_sheet.append_row([timestamp.strftime("%m/%d/%Y %H:%M:%S"), contact, 'Active'], value_input_option='USER_ENTERED')     
                
        # Send confirmation email for every order, now passing the total price
        send_bakery_email("🍞 Aiara Bakery Order Received!", contact, name, order_total)

        msg = f"Your order is in! (Note: It arrived after the {deadline_text} cutoff, so we will confirm your bake day shortly.)" if is_late else f"Thanks {name}, your order is confirmed for our next bake day!"
        
        return render_template('success.html', name=name, message=msg, is_late=is_late, details=settings, total=order_total)
    except Exception as e:
        return f"Error: {e}"
        
@app.route('/subscribe', methods=['POST'])
def subscribe():
    try:
        email = request.form.get('email').strip().lower()
        if not email:
            return redirect(url_for('home'))

        timestamp = datetime.now()
        sheet = get_sheet()
        sub_sheet = sheet.worksheet("Subscribers")
        
        try:
            # Safely grab existing emails in column B
            existing_emails = sub_sheet.col_values(2)
        except Exception:
            existing_emails = []

        # Check if they are already on the list so we don't get duplicates
        if email not in existing_emails:
            sub_sheet.append_row([
                timestamp.strftime("%m/%d/%Y %H:%M:%S"), 
                email, 
                'Active'
            ], value_input_option='USER_ENTERED')
            
        # Point back to your actual success page!
        return render_template('subscribe_success.html', email=email)
        
    except Exception as e:
        print(f"Subscribe Error: {e}")
        return redirect(url_for('home'))

@app.route('/unsubscribe', methods=['GET', 'POST'])
def unsubscribe():
    if request.method == 'POST':
        return redirect(url_for('home'))
    return render_template('unsubscribe.html')

# Important for Vercel
index = app
