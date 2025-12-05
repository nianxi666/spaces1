import requests
import hmac
import hashlib
from datetime import datetime, timedelta
from .database import load_db, save_db

def is_membership_enabled():
    """Check if membership system is enabled"""
    db = load_db()
    return db.get('membership_settings', {}).get('enabled', False)

def is_user_member(username):
    """Check if user is an active member"""
    db = load_db()
    user = db.get('users', {}).get(username)
    if not user:
        return False
    
    if not user.get('is_member', False):
        return False
    
    expiry_date = user.get('member_expiry_date')
    if not expiry_date:
        return False
    
    try:
        expiry = datetime.fromisoformat(expiry_date)
        return datetime.utcnow() < expiry
    except (ValueError, TypeError):
        return False

def get_user_membership_status(username):
    """Get detailed membership status for user"""
    db = load_db()
    user = db.get('users', {}).get(username)
    
    if not user:
        return {
            'is_member': False,
            'expiry_date': None,
            'days_remaining': 0,
            'expired': False
        }
    
    is_member = user.get('is_member', False)
    expiry_date = user.get('member_expiry_date')
    
    if not expiry_date or not is_member:
        return {
            'is_member': False,
            'expiry_date': None,
            'days_remaining': 0,
            'expired': False
        }
    
    try:
        expiry = datetime.fromisoformat(expiry_date)
        now = datetime.utcnow()
        days_remaining = (expiry - now).days
        expired = now >= expiry
        
        return {
            'is_member': is_member and not expired,
            'expiry_date': expiry_date,
            'days_remaining': max(0, days_remaining),
            'expired': expired
        }
    except (ValueError, TypeError):
        return {
            'is_member': False,
            'expiry_date': None,
            'days_remaining': 0,
            'expired': False
        }

def set_user_membership(username, duration_days=30):
    """Set user as member for specified number of days"""
    db = load_db()
    user = db.get('users', {}).get(username)
    
    if not user:
        return False
    
    expiry_date = (datetime.utcnow() + timedelta(days=duration_days)).isoformat()
    user['is_member'] = True
    user['member_expiry_date'] = expiry_date
    
    if 'payment_history' not in user:
        user['payment_history'] = []
    
    payment_record = {
        'timestamp': datetime.utcnow().isoformat(),
        'type': 'subscription',
        'duration_days': duration_days,
        'expiry_date': expiry_date
    }
    user['payment_history'].append(payment_record)
    
    save_db(db)
    return True

def revoke_user_membership(username):
    """Revoke user's membership"""
    db = load_db()
    user = db.get('users', {}).get(username)
    
    if not user:
        return False
    
    user['is_member'] = False
    user['member_expiry_date'] = None
    save_db(db)
    return True

def create_payhip_payment_link(username):
    """Create Payhip payment link for user"""
    db = load_db()
    membership_settings = db.get('membership_settings', {})
    
    if not membership_settings.get('enabled'):
        return None
    
    api_key = membership_settings.get('payhip_api_key', '').strip()
    product_id = membership_settings.get('payhip_product_id', '').strip()
    
    if not api_key or not product_id:
        return None
    
    try:
        user = db.get('users', {}).get(username)
        if not user:
            return None
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'product_id': product_id,
            'customer_email': user.get('email', f'{username}@example.com'),
            'success_url': f'/user/membership/success',
            'cancel_url': f'/user/membership/cancel',
            'metadata': {
                'username': username
            }
        }
        
        response = requests.post(
            'https://api.payhip.com/payment/create',
            json=payload,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get('payment_url') or data.get('checkout_url')
        
        return None
    except Exception as e:
        print(f"Error creating Payhip payment link: {e}")
        return None

def verify_payhip_webhook(payload, signature, api_key):
    """Verify Payhip webhook signature"""
    try:
        payload_str = str(payload)
        expected_signature = hmac.new(
            api_key.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    except Exception:
        return False

def handle_payhip_webhook(webhook_data):
    """Process Payhip webhook payment confirmation"""
    try:
        status = webhook_data.get('status')
        
        if status != 'completed':
            return False
        
        username = webhook_data.get('metadata', {}).get('username')
        if not username:
            return False
        
        db = load_db()
        membership_settings = db.get('membership_settings', {})
        duration_days = membership_settings.get('duration_days', 30)
        
        return set_user_membership(username, duration_days)
    except Exception as e:
        print(f"Error processing Payhip webhook: {e}")
        return False
