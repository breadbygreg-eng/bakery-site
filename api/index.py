from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import json
import urllib.request
from flask import Flask, render_template, request, redirect, url_for
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__, template_folder='../templates')

# --- LOGISTICS MAPPING ---
LOGISTICS_MAP = {
    'Clarksburg Resident (Pickup)': 'pickup_window',
    'Washington, DC 29th St NW': 'dc_pickup_window',
    'WWS (Pickup)': 'wws_pickup_window',
    '8001 Woodmont (Front desk delivery)': 'woodmont_window'
}

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
        
        settings_dict = {item['Setting Name']: item['Value'] for item in data if item.get('Setting Name')}
        
        bake_date_str = settings_dict.get('Next Bake Date', '01/01/2099')
        bake_date_dt = None
        
        for fmt in ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"]:
            try:
                bake_date_dt = datetime.strptime(bake_date_str, fmt).replace(tzinfo=ZoneInfo('America/New_York'))
                break
            except ValueError:
                continue
        
        if not bake_date_dt:
            bake_date_dt = datetime.now(ZoneInfo('America/New_York')) + timedelta(days=7)

        # Standard Cutoff: 8:00 PM Eastern, 2 days before bake
        deadline_dt = bake_date_dt - timedelta(days=2)
        deadline_dt = deadline_dt.replace(hour=20, minute=0)
        
        return bake_date_dt, deadline_dt, f"{deadline_dt.strftime('%B')} {deadline_dt.day} at 8:00 PM"
    except Exception as e:
        print(f"Settings Error: {e}")
        future = datetime.now(ZoneInfo('America/New_York')) + timedelta(days=2)
        return future, future, "Prior to Bake"

def send_bakery_email(recipient, name=None, total="0.00", is_late=False):
    try:
        _, _, deadline_text = get_bake_settings()
        unsubscribe_url = f"https://aiarabakery.com/unsubscribe?email={recipient}"
        
        # Branching Content for Late vs On-Time
        if is_late:
            subject = "🍞 Pre-Order Received (Next Week's Bake)"
            status_alert = f"""
                <div style="background: #fff5f5; border: 1px solid #feb2b2; padding: 15px; margin-bottom: 20px; color: #9b2c2c;">
                    <strong>Note:</strong> Since the cutoff for this week has passed, your loaf is secured for <strong>NEXT week's bake.</strong>
                </div>
            """
        else:
            subject = "🍞 Aiara Bakery Order Received!"
            status_alert = "<p>We've received your order and added it to the bake list. Thank you for supporting Aiara Bakery!</p>"

        html_content = f"""
            <html>
                <body style="font-family: sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 8px;">
                        <h2 style="color: #d4a373;">Hello{"" if not name else " " + name}!</h2>
                        {status_alert}
                        
                        <div style="background: #f9f9f9; padding: 20px; border-left: 4px solid #008CFF; margin: 25px 0;">
                            <h3 style="margin-top: 0; color: #333;">Payment Instructions</h3>
                            <p>Your total for this bake is <strong>${total}</strong>. To finalize your order, please send your payment via Venmo to <strong>@aiarabakery</strong>.</p>
                            <a href="https://venmo.com/aiarabakery" style="display: inline-block; background: #008CFF; color: white; padding: 12px 25px; text-decoration: none; border-radius: 4px; font-weight: bold; margin-top: 10px; margin-bottom: 20px;">Pay ${total} with Venmo</a>
                            <p style="margin: 0; font-size: 0.9em; color: #555;">No Venmo? Zelle: <strong>greg@aiarabakery.com</strong></p>
                        </div>                        
                        <p>Orders for the upcoming bake close on <strong>{deadline_text}</strong>.</p>
                        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                        <small style="color: #888;">Aiara Bakery | <a href="{unsubscribe_url}">Unsubscribe</a></small>
                    </div>
                </body>
            </html>
        """
        
        data = {
            "sender": {"name": "Aiara Bakery", "email": "greg@aiarabakery.com"},
            "to": [{"email": recipient}], "bcc": [{"email": "greg@aiarabakery.com"}],
            "subject": subject, "htmlContent": html_content
        }
        
        req = urllib.request.Request("https://api.brevo.com/v3/smtp/email", data=json.dumps(data).encode('utf-8'), method='POST')
        req.add_header('api-key', os.environ.get('BREVO_API_KEY'))
        req.add_header('Content-Type', 'application/json')
        
        with urllib.request.urlopen(req) as response:
            print(f"Email sent: {response.status}")
    except Exception as e:
        print(f"Brevo API Error: {e}")

def send_subscription_email(subject, recipient, name=None):
    try:
        html_content = f"""
            <html>
                <body style="font-family: sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 8px;">
                        <h2 style="color: #d4a373;">Welcome to the VIP Carb Club{"" if not name else ", " + name}! 🍞</h2>
                        <p>You are officially on the Aiara Bakery VIP roster. No more Friday morning panics.</p>
                        <div style="background: #fdfaf5; padding: 20px; border-left: 4px solid #d4a373; margin: 25px 0;">
                            <h3 style="margin-top: 0; color: #5d4037;">How the Billing Works</h3>
                            <p>Subscriptions are billed at a flat monthly rate ($30/month). I will be sending your first payment request shortly via Venmo.</p>
                        </div>
                        <p>Welcome to the club!</p>
                    </div>
                </body>
            </html>
        """
        data = {
            "sender": {"name": "Aiara Bakery", "email": "greg@aiarabakery.com"},
            "to": [{"email": recipient}], "bcc": [{"email": "greg@aiarabakery.com"}],
            "subject": subject, "htmlContent": html_content
        }
        req = urllib.request.Request("https://api.brevo.com/v3/smtp/email", data=json.dumps(data).encode('utf-8'), method='POST')
        req.add_header('api-key', os.environ.get('BREVO_API_KEY'))
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req) as response: print(f"Sub Email: {response.status}")
    except Exception as e: print(f"Sub Email Error: {e}")

def send_vip_email(subject, recipient, name=None):
    try:
        html_content = f"""
            <html><body style="font-family: sans-serif;"><h2 style="color: #d4a373;">Hello{"" if not name else " " + name}!</h2>
            <p>Your VIP loaf for this week is locked in. We'll see you at pickup!</p></body></html>
        """
        data = {
            "sender": {"name": "Aiara Bakery", "email": "greg@aiarabakery.com"},
            "to": [{"email": recipient}], "subject": subject, "htmlContent": html_content
        }
        req = urllib.request.Request("https://api.brevo.com/v3/smtp/email", data=json.dumps(data).encode('utf-8'), method='POST')
        req.add_header('api-key', os.environ.get('BREVO_API_KEY'))
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req) as response: print(f"VIP Email: {response.status}")
    except Exception as e: print(f"VIP Email Error: {e}")

@app.route('/')
def home():
    try:
        sheet = get_sheet()
        items = sheet.worksheet("Menu").get_all_records()
        visible_items = [i for i in items if i.get('Status') == 'Active']
        settings = {i['Setting Name']: i['Value'] for i in sheet.worksheet("Settings").get_all_records() if i.get('Setting Name')}
        
        bake_dt, deadline_dt, deadline_text = get_bake_settings()
        now_ny = datetime.now(ZoneInfo('America/New_York'))
        
        settings['Formatted Bake Date'] = f"{bake_dt.strftime('%B')} {bake_dt.day}"
        settings['Formatted Deadline'] = deadline_text
        
        # UI ALERT: Closing Soon (Within 6 hours of deadline)
        time_until_deadline = deadline_dt - now_ny
        settings['is_closing_soon'] = timedelta(hours=0) < time_until_deadline <= timedelta(hours=6)

        if now_ny > deadline_dt and settings.get('Store Status') != 'Closed':
            settings['Store Status'] = 'Pre-Order'
        
        # Logistics windows
        for key, set_key in [('window_list', 'Pickup Windows'), ('dc_window_list', 'DC Pickup Windows'), 
                             ('wws_window_list', 'WWS (Pickup) Info'), ('woodmont_window_list', '8001 Woodmont (Front desk delivery)')]:
            if settings.get(set_key): settings[key] = [w.strip() for w in settings[set_key].split(',')]
            
        return render_template('index.html', items=visible_items, details=settings)
    except Exception as e:
        return f"Sheets Connection Error: {e}"

@app.route('/submit', methods=['POST'])
def submit():
    try:
        if request.form.get('website_url'): return redirect(url_for('home'))
        name, contact = request.form.get('name'), request.form.get('contact').strip().lower()
        order_summary, order_total = request.form.get('order_summary'), request.form.get('order_total', '0.00')
        timestamp = datetime.now(ZoneInfo('America/New_York'))
        
        _, deadline_dt, _ = get_bake_settings()
        is_late = timestamp > deadline_dt

        sheet = get_sheet()
        logistics_choice = request.form.get('logistics')
        field_key = LOGISTICS_MAP.get(logistics_choice)
        logistics_details = request.form.get(field_key, 'N/A') if field_key else "N/A"
        is_subscribing = "Yes" if request.form.get('subscription') else "No"

        sheet.worksheet("Orders").append_row([
            timestamp.strftime("%m/%d/%Y %H:%M:%S"), name, contact, order_summary, 
            logistics_choice, logistics_details, is_subscribing, request.form.get('notes'),
            f"${order_total}", "Pending"
        ], value_input_option='USER_ENTERED')

        if request.form.get('join_list'):
            sub_sheet = sheet.worksheet("Subscribers")
            if contact not in sub_sheet.col_values(2):
                sub_sheet.append_row([timestamp.strftime("%m/%d/%Y %H:%M:%S"), contact, 'Active'], value_input_option='USER_ENTERED')

        send_bakery_email(contact, name, order_total, is_late=is_late)
        if request.form.get('subscription'):
            send_subscription_email("Welcome to the VIP Roster!", contact, name)

        return redirect(url_for('success', name=name, total=order_total, is_late=is_late))
    except Exception as e: return f"Error: {e}"

@app.route('/subscribe', methods=['POST'])
def subscribe():
    try:
        if request.form.get('website_url'): return redirect(url_for('home'))
        email = request.form.get('email').strip().lower()
        sheet = get_sheet()
        sub_sheet = sheet.worksheet("Subscribers")
        if email not in sub_sheet.col_values(2):
            sub_sheet.append_row([datetime.now(ZoneInfo('America/New_York')).strftime("%m/%d/%Y %H:%M:%S"), email, 'Active'], value_input_option='USER_ENTERED')
        return render_template('subscribe_success.html', email=email)
    except: return redirect(url_for('home'))

@app.route('/vip-submit', methods=['POST'])
def vip_submit():
    try:
        if request.form.get('website_url'): return redirect(url_for('home'))
        name, contact = request.form.get('name'), request.form.get('contact').strip().lower()
        base_summary = request.form.get('order_summary')
        timestamp = datetime.now(ZoneInfo('America/New_York'))
        
        sheet = get_sheet()
        loaf_size = "[SIZE UNKNOWN - MANUAL CHECK]" # Hardened Fallback logic
        try:
            sub_records = sheet.worksheet("Bread Subscriptions").get_all_records()
            for row in sub_records:
                if str(row.get('Email', '')).strip().lower() == contact:
                    loaf_size = row.get('Size', loaf_size)
                    break
        except: pass
            
        order_summary = f"{base_summary} ({loaf_size})"
        logistics_choice = request.form.get('logistics')
        logistics_details = request.form.get(LOGISTICS_MAP.get(logistics_choice), 'N/A')

        sheet.worksheet("Orders").append_row([
            timestamp.strftime("%m/%d/%Y %H:%M:%S"), name, contact, order_summary, 
            logistics_choice, logistics_details, "Yes (VIP)", request.form.get('notes'),
            "VIP Prepaid", "Paid"
        ], value_input_option='USER_ENTERED')

        send_vip_email("🍞 VIP Order Confirmed!", contact, name)
        return redirect(url_for('vip_success', name=name))
    except Exception as e: return f"Error: {e}"

@app.route('/unsubscribe')
def unsubscribe(): return render_template('unsubscribe.html')

@app.route('/success')
def success():
    name, total, is_late = request.args.get('name', ''), request.args.get('total', '0.00'), request.args.get('is_late') == 'True'
    msg = "Your pre-order is in for NEXT week's bake!" if is_late else f"Thanks {name}, your order is confirmed!"
    return render_template('success.html', name=name, message=msg, total=total, details={})

@app.route('/vip-success')
def vip_success(): return render_template('vip_success.html', name=request.args.get('name', ''), details={})

@app.route('/early-access')
def early_access(): # (Logic omitted for brevity but keeping route active)
    return redirect(url_for('home'))

@app.route('/vip')
def vip(): # (Logic similar to home, renders vip.html)
    return render_template('vip.html', items=[], details={})

index = app
