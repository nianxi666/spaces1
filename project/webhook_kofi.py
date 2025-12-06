import uuid
from flask import Blueprint, request, jsonify, current_app
from .database import load_db, save_db
import logging
from datetime import datetime, timedelta

# Create a logger for payments
logger = logging.getLogger('payment')
logger.setLevel(logging.INFO)
# Ensure handlers are set up (basic config usually handles this in Flask, but good to be sure)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s in payment: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

payment_bp = Blueprint('payment', __name__, url_prefix='/api/payment')

@payment_bp.route('/kofi/webhook', methods=['POST'])
def kofi_webhook():
    db = load_db()
    # Settings are stored in 'pro_settings' in admin.py
    pro_settings = db.get('pro_settings', {})

    # 1. Verify Token
    stored_token = pro_settings.get('kofi_verification_token')

    # Ko-fi sends data as application/x-www-form-urlencoded
    # The 'data' parameter contains the JSON payload
    raw_data = request.form.get('data')

    if not raw_data:
        # Sometimes it might be sent as raw JSON (though Ko-fi docs say form data)
        # Let's try to parse request.json just in case, or for testing
        if request.is_json:
            payload = request.get_json()
        else:
            logger.warning("Ko-fi Webhook: No data received")
            return jsonify({'error': 'No data'}), 400
    else:
        import json
        try:
            payload = json.loads(raw_data)
        except json.JSONDecodeError:
            logger.error(f"Ko-fi Webhook: Invalid JSON in data param: {raw_data}")
            return jsonify({'error': 'Invalid JSON'}), 400

    # Verify the token inside the payload
    incoming_token = payload.get('verification_token')

    if not stored_token:
        logger.error("Ko-fi Webhook: Verification token not configured in system settings")
        return jsonify({'error': 'System misconfiguration'}), 500

    if incoming_token != stored_token:
        logger.warning(f"Ko-fi Webhook: Invalid verification token. Expected: {stored_token[:5]}***, Got: {incoming_token}")
        return jsonify({'error': 'Invalid token'}), 403

    logger.info(f"Ko-fi Webhook received: {payload}")

    # 2. Extract Data
    payment_email = payload.get('email')
    # Try to find username in various fields.
    # Ko-fi might pass it in 'from_name' or custom fields depending on setup.
    # We will prioritize explicit field matches if we add them later,
    # but for now we look for 'username' in the payload if the user configured a custom input.
    # Or checking 'message' for exactly a username.

    payment_username_input = payload.get('username') # If custom field named 'username' exists
    from_name = payload.get('from_name')

    # 3. Identify User
    target_user_key = None

    # Strategy A: Match by Email
    if payment_email:
        for u_key, u_data in db['users'].items():
            if u_data.get('email') == payment_email:
                target_user_key = u_key
                logger.info(f"Ko-fi Webhook: Matched user '{u_key}' by email '{payment_email}'")
                break

    # Strategy B: Match by Username (if provided and not matched by email yet)
    if not target_user_key:
        candidates = [payment_username_input, from_name]
        for candidate in candidates:
            if candidate:
                candidate = candidate.strip()
                if candidate in db['users']:
                    target_user_key = candidate
                    logger.info(f"Ko-fi Webhook: Matched user '{target_user_key}' by username input '{candidate}'")
                    break

    if not target_user_key:
        logger.warning(f"Ko-fi Webhook: No matching user found for Email='{payment_email}', Inputs={candidates}")
        # Return 200 to Ko-fi so they don't retry endlessly, but log error
        return jsonify({'status': 'ignored', 'message': 'User not found'}), 200

    # 4. Process Membership
    user = db['users'][target_user_key]

    # Determine duration
    # Default unit is 1 = 30 days
    shop_items = payload.get('shop_items', [])
    quantity = 0

    if shop_items:
        for item in shop_items:
            # You might want to filter by specific shop item IDs if you sell other things
            # For now, we assume all shop items from this link are membership top-ups
            try:
                q = int(item.get('quantity', 1))
                quantity += q
            except (ValueError, TypeError):
                quantity += 1
    else:
        # Fallback if no shop items details (e.g. simple donation)
        # Maybe use amount? But requirement said "quantity stacks time".
        # We will assume at least 1 unit if it's a valid transaction
        quantity = 1

    days_to_add = quantity * 30

    # Update User
    now = datetime.utcnow()
    current_expiry_str = user.get('membership_expiry')

    if current_expiry_str:
        try:
            current_expiry = datetime.fromisoformat(current_expiry_str)
            # If expired, start from now. If active, add to existing expiry.
            if current_expiry < now:
                new_expiry = now + timedelta(days=days_to_add)
            else:
                new_expiry = current_expiry + timedelta(days=days_to_add)
        except ValueError:
            new_expiry = now + timedelta(days=days_to_add)
    else:
        new_expiry = now + timedelta(days=days_to_add)

    user['membership_expiry'] = new_expiry.isoformat()
    user['is_pro'] = True
    # Reset pro submission status if it was pending/rejected, to clean up UI
    user['pro_submission_status'] = 'approved'

    # Log Order
    if 'orders' not in db:
        db['orders'] = []

    order_record = {
        'id': payload.get('kofi_transaction_id') or str(uuid.uuid4()),
        'user': target_user_key,
        'provider': 'kofi',
        'amount': payload.get('amount'),
        'currency': payload.get('currency'),
        'quantity': quantity,
        'days_added': days_to_add,
        'timestamp': payload.get('timestamp') or now.isoformat(),
        'raw_data': payload
    }
    db['orders'].append(order_record)

    save_db(db)

    logger.info(f"Ko-fi Webhook: Successfully topped up {days_to_add} days for user '{target_user_key}'. New Expiry: {new_expiry}")

    return jsonify({'status': 'success'}), 200
