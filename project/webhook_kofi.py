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

def log_webhook_event(payload, status, message, order_id=None):
    """
    Logs every webhook event (success or failure) to the database for auditing and manual recovery.
    """
    try:
        db = load_db()
        if 'webhook_events' not in db:
            db['webhook_events'] = []

        event = {
            'id': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat(),
            'payload': payload,
            'status': status, # 'success', 'ignored', 'error'
            'message': message,
            'order_id': order_id,
            'is_recovered': False
        }

        # Prepend to list
        db['webhook_events'].insert(0, event)

        # Limit to 100 entries to prevent DB bloat
        if len(db['webhook_events']) > 100:
            db['webhook_events'] = db['webhook_events'][:100]

        save_db(db)
        return event['id']
    except Exception as e:
        logger.error(f"Failed to log webhook event: {e}")
        return None

def process_membership_topup(user, payload, order_id_override=None):
    """
    Core logic to top up membership given a user object and payload.
    Returns the order object.
    """
    now = datetime.utcnow()

    # Determine duration
    shop_items = payload.get('shop_items', [])
    quantity = 0

    if shop_items:
        for item in shop_items:
            try:
                q = int(item.get('quantity', 1))
                quantity += q
            except (ValueError, TypeError):
                quantity += 1
    else:
        quantity = 1

    days_to_add = quantity * 30

    # Update User
    current_expiry_str = user.get('membership_expiry')

    if current_expiry_str:
        try:
            current_expiry = datetime.fromisoformat(current_expiry_str)
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
    user['pro_submission_status'] = 'approved'

    # Create Order Record
    order_record = {
        'id': order_id_override or payload.get('kofi_transaction_id') or str(uuid.uuid4()),
        'username': user.get('username', 'unknown'), # Ensure username is captured if user obj comes from dict iteration
        'user': user.get('username', 'unknown'), # Legacy support? Or just naming confusion
        'provider': 'kofi',
        'amount': payload.get('amount'),
        'currency': payload.get('currency'),
        'quantity': quantity,
        'days_added': days_to_add,
        'timestamp': payload.get('timestamp') or now.isoformat(),
        'raw_data': payload
    }

    return order_record

@payment_bp.route('/kofi/webhook', methods=['POST'])
def kofi_webhook():
    db = load_db()
    pro_settings = db.get('pro_settings', {})
    stored_token = pro_settings.get('kofi_verification_token')

    raw_data = request.form.get('data')
    payload = {}

    if not raw_data:
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
            logger.error(f"Ko-fi Webhook: Invalid JSON: {raw_data}")
            return jsonify({'error': 'Invalid JSON'}), 400

    incoming_token = payload.get('verification_token')

    if not stored_token:
        msg = "Verification token not configured"
        logger.error(f"Ko-fi Webhook: {msg}")
        log_webhook_event(payload, 'error', msg)
        return jsonify({'error': msg}), 500

    if incoming_token != stored_token:
        msg = "Invalid verification token"
        logger.warning(f"Ko-fi Webhook: {msg}")
        log_webhook_event(payload, 'error', msg)
        return jsonify({'error': msg}), 403

    logger.info(f"Ko-fi Webhook received: {payload}")

    payment_email = payload.get('email')
    payment_username_input = payload.get('username')
    from_name = payload.get('from_name')

    target_user_key = None

    # Strategy A: Email
    if payment_email:
        for u_key, u_data in db['users'].items():
            if u_data.get('email') == payment_email:
                target_user_key = u_key
                break

    # Strategy B: Username (Exact & Case-Insensitive)
    if not target_user_key:
        candidates = [payment_username_input, from_name]
        valid_candidates = [c.strip() for c in candidates if c]

        for candidate in valid_candidates:
            # Exact match
            if candidate in db['users']:
                target_user_key = candidate
                break

            # Case-insensitive match
            candidate_lower = candidate.lower()
            for u_key in db['users'].keys():
                if u_key.lower() == candidate_lower:
                    target_user_key = u_key
                    break
            if target_user_key:
                break

    # If still not found, log ignored event
    if not target_user_key:
        msg = f"User not found for Email='{payment_email}', Names={valid_candidates}"
        logger.warning(f"Ko-fi Webhook: {msg}")
        log_webhook_event(payload, 'ignored', msg)
        return jsonify({'status': 'ignored', 'message': 'User not found'}), 200

    # Process Success
    user = db['users'][target_user_key]
    # Ensure username key is available in user object for processing function if needed
    if 'username' not in user:
        user['username'] = target_user_key

    order_record = process_membership_topup(user, payload)

    if 'orders' not in db:
        db['orders'] = []
    db['orders'].append(order_record)

    save_db(db)

    log_webhook_event(payload, 'success', f"Topped up {order_record['days_added']} days for {target_user_key}", order_id=order_record['id'])
    logger.info(f"Ko-fi Webhook: Success for user '{target_user_key}'")

    return jsonify({'status': 'success'}), 200

@payment_bp.route('/recover_order', methods=['POST'])
def recover_order():
    """
    Admin endpoint to manually recover/process a stored webhook event.
    """
    from flask import session
    if not session.get('logged_in') or not session.get('is_admin'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    data = request.get_json()
    event_id = data.get('event_id')
    target_username = data.get('target_username')

    if not event_id or not target_username:
        return jsonify({'success': False, 'error': 'Missing parameters'}), 400

    db = load_db()

    # Find event
    events = db.get('webhook_events', [])
    event = next((e for e in events if e['id'] == event_id), None)

    if not event:
        return jsonify({'success': False, 'error': 'Event not found'}), 404

    if event.get('is_recovered'):
        return jsonify({'success': False, 'error': 'Event already recovered'}), 400

    # Find User
    user = db['users'].get(target_username)
    if not user:
        return jsonify({'success': False, 'error': 'Target user not found'}), 404

    # Process
    if 'username' not in user:
        user['username'] = target_username

    order_record = process_membership_topup(user, event['payload'])

    if 'orders' not in db:
        db['orders'] = []
    db['orders'].append(order_record)

    # Update Event Status
    event['is_recovered'] = True
    event['recovered_by'] = session.get('username')
    event['recovered_at'] = datetime.utcnow().isoformat()
    event['order_id'] = order_record['id']
    event['message'] += f" [Manually Recovered to {target_username}]"
    event['status'] = 'recovered'
    event['assigned_to'] = target_username  # IMPORTANT: Add this field for tracking

    save_db(db)

    return jsonify({'success': True, 'message': f'Order recovered for {target_username}'})
