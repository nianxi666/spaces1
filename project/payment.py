from flask import Blueprint, request, jsonify, current_app
from .database import load_db, save_db
from datetime import datetime, timedelta
import logging
import requests

payment_bp = Blueprint('payment', __name__, url_prefix='/api/payment')

@payment_bp.route('/gumroad/webhook', methods=['POST'])
def gumroad_webhook():
    """
    Handles Webhook events from Gumroad.
    Supports 'ping' (sale) and 'cancellation'/'refund' events.
    """
    db = load_db()
    settings = db.get('payment_settings', {})

    # Check if payment system is enabled
    if not settings.get('enabled'):
        return jsonify({'error': 'Payment system disabled'}), 503

    # Basic verification logic (Gumroad doesn't sign requests by default unless configured,
    # but we can check if the product matches ours if we wanted strictly.
    # However, for now we will rely on the post data).
    # Ideally, we should check against a 'resource_url' or similar, but the most important
    # part is linking the sale to a user via custom_fields.

    data = request.form

    # Security: Verify Sale ID against Gumroad API to prevent spoofing
    # We use the sale_id (or id) to query the Gumroad API.
    # If the API returns a valid sale for this ID, we trust it.
    sale_id = data.get('sale_id') or data.get('id')
    if not sale_id:
        # If no sale_id, we can't verify. For 'cancellation', it might use subscription_id
        # But 'ping' usually has a sale_id.
        return jsonify({'error': 'Missing sale_id for verification'}), 400

    access_token = settings.get('gumroad_access_token')
    if access_token:
        # Only verify if we have an access token. If not configured, we skip (insecure but allows testing)
        # In production, this should be enforced.
        try:
            import requests
            verify_url = f"https://api.gumroad.com/v2/sales/{sale_id}"
            verify_response = requests.get(verify_url, params={'access_token': access_token})

            if verify_response.status_code != 200:
                logging.error(f"Gumroad verification failed for sale {sale_id}: {verify_response.text}")
                return jsonify({'error': 'Verification failed: Sale not found'}), 403

            verified_sale = verify_response.json().get('sale', {})
            # Optional: Check if the product permalink matches
            # if verified_sale.get('product_permalink') != data.get('permalink'): ...

        except Exception as e:
            logging.error(f"Error during Gumroad verification: {e}")
            return jsonify({'error': 'Verification error'}), 500

    # Extract event type
    # Gumroad sends resource_name='sale' usually.
    resource_name = data.get('resource_name')

    # Check for test mode if necessary
    # is_test = data.get('test') == 'true'

    # 1. Identify User
    # We expect custom_fields[user_id] or custom_fields[username]
    # Gumroad sends these as 'custom_fields[user_id]' keys in the form data.
    user_identifier = data.get('custom_fields[user_id]') or data.get('custom_fields[username]')
    order_id = data.get('custom_fields[order_id]')

    if not user_identifier:
        # Try finding by email if no custom field (less reliable if email differs)
        email = data.get('email')
        if email:
            # Search user by email (not indexed, slow linear search but okay for low volume)
            # Assuming we don't store email in user object explicitly?
            # We assume user_identifier is passed. If not, we can't link.
            pass

        if not user_identifier:
            return jsonify({'error': 'No user identifier provided in custom_fields'}), 400

    # Find user in DB
    # Check if identifier is a username directly
    user = db['users'].get(user_identifier)
    username = user_identifier

    # If not found by username, maybe it was an ID?
    # Current system uses username as primary key mostly, but let's assume username was passed.
    if not user:
        # Search by ID if we had IDs, but here we use username as key usually.
        # Let's try to match if user_identifier matches any user's email or something if needed.
        # For now, strict match on username.
        return jsonify({'error': f'User {user_identifier} not found'}), 404

    # 2. Handle Sale (New Subscription or One-time)
    # Gumroad events:
    # - sale: New purchase
    # - recurrence: Subscription renewal? (Gumroad usually just sends 'sale' again for recurrence or has specific hooks)
    # - cancellation: Subscription cancelled
    # - refund: Money returned

    # For subscription, we might look at 'cancellation' or 'refund'.
    # A successful charge usually comes as a 'sale'.

    is_refund = data.get('refund') == 'true'
    is_cancelled = data.get('cancelled') == 'true'
    # 'disputed' might also be a field.

    if is_refund or is_cancelled:
        # Update Order Status
        if order_id and order_id in db.get('orders', {}):
            db['orders'][order_id]['status'] = 'refunded' if is_refund else 'cancelled'
            db['orders'][order_id]['updated_at'] = datetime.utcnow().isoformat()

        # Downgrade user
        user['is_pro'] = False
        user['membership_status'] = 'free'
        # We might want to keep the expiry date if it was just cancelled but not refunded (access until end of period),
        # but Gumroad's 'cancelled' usually means "turn off auto-renew".
        # If we want to support "access until end of term", we need to parse 'ends_at' if provided,
        # or calculate based on last payment.
        # For simplicity in this iteration: If refunded -> immediate removal. If cancelled -> let it run?

        # If specifically REFUNDED, revoke immediately.
        if is_refund:
            user['is_pro'] = False
            user['membership_status'] = 'free'
            user['membership_expiry'] = datetime.utcnow().isoformat() # Expire now

        # If CANCELLED (auto-renew off), we ideally keep them Pro until the paid period ends.
        # Gumroad doesn't always send the "end date" easily in the webhook.
        # We will trust the "membership_expiry" we calculated during the sale event.
        # But we should mark that they have cancelled so we don't expect future payments.
        # Update: Gumroad sends 'cancelled' event.

    else:
        # It's a valid sale/renewal
        product_permalink = data.get('permalink')
        # Optional: Verify product matches config
        # expected_product = settings.get('gumroad_product_url', '').split('/')[-1]
        # if expected_product and product_permalink != expected_product:
        #    return jsonify({'error': 'Product mismatch'}), 400

        user['is_pro'] = True
        user['membership_status'] = 'pro'
        user['gumroad_subscriber_id'] = data.get('subscriber_id') or data.get('sale_id')

        # Calculate Expiry
        # Default to 31 days from now for a monthly sub
        expiry_date = datetime.utcnow() + timedelta(days=32)
        user['membership_expiry'] = expiry_date.isoformat()

        # Update Order Status
        if order_id:
            if 'orders' not in db:
                db['orders'] = {}

            if order_id in db['orders']:
                # Convert price to integer/float if necessary, Gumroad sends strings usually.
                # 'price' is typically in cents for cents-based currencies or unit amount.
                # Assuming data.get('price') returns a string or int.
                try:
                    price = int(data.get('price', 0))
                except (ValueError, TypeError):
                    price = 0

                db['orders'][order_id]['status'] = 'paid'
                db['orders'][order_id]['gumroad_sale_id'] = sale_id
                db['orders'][order_id]['amount'] = price
                db['orders'][order_id]['currency'] = data.get('currency', 'usd')
                db['orders'][order_id]['updated_at'] = datetime.utcnow().isoformat()
            else:
                try:
                    price = int(data.get('price', 0))
                except (ValueError, TypeError):
                    price = 0

                # Order ID exists in payload but not in DB? Strange, maybe expired or manual link.
                # Create a new record for tracking
                db['orders'][order_id] = {
                    'id': order_id,
                    'user_id': username,
                    'status': 'paid',
                    'amount': price,
                    'currency': data.get('currency', 'usd'),
                    'gumroad_sale_id': sale_id,
                    'created_at': datetime.utcnow().isoformat(),
                    'updated_at': datetime.utcnow().isoformat()
                }
        else:
            try:
                price = int(data.get('price', 0))
            except (ValueError, TypeError):
                price = 0

            # No Order ID provided (Direct link?), create a new "paid" order entry to track it
            import uuid
            new_order_id = str(uuid.uuid4())
            if 'orders' not in db:
                db['orders'] = {}
            db['orders'][new_order_id] = {
                'id': new_order_id,
                'user_id': username,
                'status': 'paid',
                'amount': price,
                'currency': data.get('currency', 'usd'),
                'gumroad_sale_id': sale_id,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }

    save_db(db)
    return jsonify({'success': True})

@payment_bp.route('/create_order', methods=['POST'])
def create_order():
    """
    Creates a pending order and redirects user to Gumroad.
    """
    from flask import session
    import uuid
    from urllib.parse import quote

    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    db = load_db()
    settings = db.get('payment_settings', {})

    if not settings.get('enabled'):
        return jsonify({'success': False, 'error': 'Payment system disabled'}), 503

    username = session['username']
    order_id = str(uuid.uuid4())

    # Create Pending Order
    if 'orders' not in db:
        db['orders'] = {}

    db['orders'][order_id] = {
        'id': order_id,
        'user_id': username,
        'status': 'pending',
        'amount': 500, # Default assumption (cents) or 5.00 depending on Gumroad
        'currency': 'usd',
        'created_at': datetime.utcnow().isoformat()
    }

    save_db(db)

    # Construct Gumroad URL
    product_url = settings.get('gumroad_product_url', '')
    if not product_url:
        return jsonify({'success': False, 'error': 'Product URL not configured'}), 500

    separator = '&' if '?' in product_url else '?'

    # URL Encode parameters
    params = f"custom_fields[user_id]={quote(username)}&custom_fields[order_id]={order_id}"
    redirect_url = f"{product_url}{separator}{params}"

    return jsonify({'success': True, 'redirect_url': redirect_url})
