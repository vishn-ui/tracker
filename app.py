from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import tracker
import tracker_db
import telegram_bot
from datetime import datetime
import os
from dotenv import load_dotenv
from urllib.parse import urlparse
from flask_dance.contrib.google import make_google_blueprint, google
import asyncio

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-in-case-of-no-env')
scheduler = BackgroundScheduler(daemon=True)
tracker_db.init_db()

# Google OAuth setup
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # For local development only

google_bp = make_google_blueprint(
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    scope=["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"],
    redirect_url="/"
)
# Force Google to show account chooser
google_bp.session.authorization_url_params = {"prompt": "select_account"}
app.register_blueprint(google_bp, url_prefix="/login")

@app.route("/login")
def login():
    if not google.authorized:
        return redirect(url_for("google.login"))
    try:
        resp = google.get("/oauth2/v2/userinfo")
        if resp.ok:
            user_info = resp.json()
            session["email"] = user_info["email"]
            session["name"] = user_info.get("name", "User")
            tracker_db.add_user(email=user_info["email"], name=user_info.get("name"))
    except Exception as e:
        print(f"Error fetching user info: {e}")
    return redirect(url_for("index"))

def get_platform_from_url(url):
    domain = urlparse(url).netloc.lower()
    if 'amazon' in domain:
        return 'Amazon'
    elif 'ebay' in domain:
        return 'eBay'
    elif 'bestbuy' in domain:
        return 'Best Buy'
    elif 'walmart' in domain:
        return 'Walmart'
    return 'Other'

async def check_price(user_id, product_id, user_product_id, url):
    """Checks a product's price and sends an alert if it's below the target."""
    print(f"Checking price for: {url}")
    try:
        title, price, image_url = tracker.get_product_price(url)
        if title and price:
            tracker_db.add_price_entry(product_id, price)
            tracker_db.update_product_last_checked(product_id)

            conn = tracker_db.get_connection()
            c = conn.cursor()
            c.execute('SELECT target_price FROM user_products WHERE id = ?', (user_product_id,))
            target_price_row = c.fetchone()
            conn.close()

            if target_price_row and target_price_row[0] is not None:
                target_price = target_price_row[0]
                history = tracker_db.get_price_history_by_url(url)
                
                # Alert only if the price just dropped below the target
                if len(history) > 1:
                    previous_price = history[-2]['price']
                    if price <= target_price and previous_price > target_price:
                        platform = get_platform_from_url(url)
                        message = telegram_bot.format_price_alert(title, price, url, platform, target_price)
                        await telegram_bot.send_notification(message)
    except Exception as e:
        print(f"Error in check_price for {url}: {str(e)}")

def schedule_price_check(user_id, product_id, user_product_id, url):
    """Adds or updates a recurring job to check a product's price."""
    job_id = f'price_check_{user_product_id}'
    scheduler.add_job(
        func=lambda: asyncio.run(check_price(user_id, product_id, user_product_id, url)),
        trigger='interval',
        hours=1,
        id=job_id,
        replace_existing=True
    )
    print(f"Scheduled job {job_id}")

def setup_initial_jobs():
    """Schedules jobs for all products in the database on startup."""
    with app.app_context():
        all_tracked = tracker_db.get_all_user_products()
        for user_id, product_id, user_product_id, url in all_tracked:
            schedule_price_check(user_id, product_id, user_product_id, url)

@app.route('/', methods=['GET', 'POST'])
async def index():
    error_message = None
    tracked_products = []
    email = session.get('email')
    name = session.get('name')

    # If not logged in, redirect to login
    if not email:
        return redirect(url_for("login"))

    if request.method == 'POST' and email:
        url = request.form.get('url')
        target_price_str = request.form.get('target_price')
        target_price = float(target_price_str) if target_price_str else None

        try:
            title, price, image_url = tracker.get_product_price(url)
            if not title or not price:
                error_message = "Could not retrieve product details. Please check the URL."
            else:
                platform = get_platform_from_url(url)
                user_id = tracker_db.get_user_id_by_email(email)
                product_id = tracker_db.add_product(title, url, image_url, platform)
                user_product_id = tracker_db.add_user_product(user_id, product_id, target_price)
                tracker_db.add_price_entry(product_id, price)
                
                # Send confirmation notification
                message = telegram_bot.format_product_notification(title, price, url, platform)
                await telegram_bot.send_notification(message)
                
                # Schedule recurring checks
                schedule_price_check(user_id, product_id, user_product_id, url)
                return redirect(url_for('index'))
        except Exception as e:
            error_message = f"An error occurred: {str(e)}"
            
    if email:
        user_id = tracker_db.get_user_id_by_email(email)
        if user_id:
            user_products_data = tracker_db.get_products_by_user_id_with_latest_price(user_id)
            for row in user_products_data:
                title, url, image_url, target_price, platform, current_price = row
                tracked_products.append({
                    'title': title,
                    'current_price': current_price,
                    'url': url,
                    'email': email,
                    'name': name,
                    'preferred_site': platform,
                    'target_price': target_price,
                    'image_url': image_url
                })

    return render_template(
        "index.html",
        error_message=error_message,
        tracked_products=tracked_products
    )

@app.route('/api/price-history')
def api_get_price_history():
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "URL parameter is required"}), 400
    history = tracker_db.get_price_history_by_url(url)
    return jsonify(history)

@app.route('/remove', methods=['POST'])
def remove():
    url = request.form.get('url')
    email = session.get('email')
    if url and email:
        try:
            conn = tracker_db.get_connection()
            c = conn.cursor()
            c.execute('SELECT id FROM users WHERE email = ?', (email,))
            user_row = c.fetchone()
            c.execute('SELECT id FROM products WHERE url = ?', (url,))
            product_row = c.fetchone()
            if user_row and product_row:
                user_id, product_id = user_row[0], product_row[0]
                c.execute('SELECT id FROM user_products WHERE user_id = ? AND product_id = ?', (user_id, product_id))
                up_row = c.fetchone()
                if up_row:
                    user_product_id = up_row[0]
                    # Remove scheduled job first
                    try:
                        scheduler.remove_job(f'price_check_{user_product_id}')
                        print(f"Removed job price_check_{user_product_id}")
                    except Exception as e:
                        print(f"Could not remove job for user_product_id {user_product_id}: {e}")
                    
                    c.execute('DELETE FROM user_products WHERE id = ?', (user_product_id,))
                    conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error removing product: {str(e)}")
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == "__main__":
    scheduler.start()
    setup_initial_jobs()
    app.run(debug=True, port=5001)