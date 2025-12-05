import requests
import hmac
import hashlib
import uuid
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

# ============ 订单管理功能 ============

def initialize_orders_table():
    """Initialize orders table if not exists"""
    db = load_db()
    if 'orders' not in db:
        db['orders'] = {}
    save_db(db)

def create_order(username):
    """Create a new payment order for user"""
    db = load_db()
    
    if 'orders' not in db:
        db['orders'] = {}
    
    # 检查用户未支付订单数量
    user_pending_orders = get_user_pending_orders(username)
    if len(user_pending_orders) >= 2:
        return None, f"已有 {len(user_pending_orders)} 个未支付订单，最多只能有 2 个"
    
    order_id = str(uuid.uuid4())
    order = {
        'order_id': order_id,
        'username': username,
        'status': 'unpaid',
        'created_at': datetime.utcnow().isoformat(),
        'expires_at': (datetime.utcnow() + timedelta(minutes=30)).isoformat(),
        'payment_url': None,
        'paid_at': None,
        'price': None,
        'currency': 'USD'
    }
    
    db['orders'][order_id] = order
    save_db(db)
    
    return order, None

def get_order(order_id):
    """Get order by ID"""
    db = load_db()
    return db.get('orders', {}).get(order_id)

def get_user_orders(username, status=None):
    """Get all orders for a user, optionally filtered by status"""
    db = load_db()
    user_orders = []
    
    for order_id, order in db.get('orders', {}).items():
        if order.get('username') == username:
            if status is None or order.get('status') == status:
                user_orders.append(order)
    
    # Sort by creation time, newest first
    return sorted(user_orders, key=lambda x: x.get('created_at', ''), reverse=True)

def get_user_pending_orders(username):
    """Get all pending (unpaid) orders for a user"""
    return get_user_orders(username, status='unpaid')

def update_order_payment_url(order_id, payment_url):
    """Update order with payment URL"""
    db = load_db()
    order = db.get('orders', {}).get(order_id)
    
    if not order:
        return False
    
    order['payment_url'] = payment_url
    save_db(db)
    return True

def mark_order_paid(order_id, username=None):
    """Mark order as paid and activate membership"""
    db = load_db()
    order = db.get('orders', {}).get(order_id)
    
    if not order:
        return False
    
    if order.get('status') != 'unpaid':
        return False
    
    order['status'] = 'paid'
    order['paid_at'] = datetime.utcnow().isoformat()
    
    # Activate membership for user
    order_username = order.get('username')
    membership_settings = db.get('membership_settings', {})
    duration_days = membership_settings.get('duration_days', 30)
    
    success = set_user_membership(order_username, duration_days)
    
    if success:
        save_db(db)
    
    return success

def cancel_order(order_id):
    """Cancel an unpaid order"""
    db = load_db()
    order = db.get('orders', {}).get(order_id)
    
    if not order:
        return False
    
    if order.get('status') != 'unpaid':
        return False
    
    order['status'] = 'cancelled'
    save_db(db)
    return True

def auto_close_expired_orders():
    """Auto-close orders that expired (30 minutes without payment)"""
    db = load_db()
    now = datetime.utcnow()
    closed_count = 0
    
    for order_id, order in db.get('orders', {}).items():
        if order.get('status') != 'unpaid':
            continue
        
        try:
            expires_at = datetime.fromisoformat(order.get('expires_at', ''))
            if now >= expires_at:
                order['status'] = 'expired'
                closed_count += 1
        except (ValueError, TypeError):
            pass
    
    if closed_count > 0:
        save_db(db)
    
    return closed_count

def get_all_orders(filter_status=None, limit=100):
    """Get all orders, optionally filtered by status"""
    db = load_db()
    all_orders = []
    
    for order_id, order in db.get('orders', {}).items():
        if filter_status is None or order.get('status') == filter_status:
            all_orders.append(order)
    
    # Sort by creation time, newest first
    all_orders = sorted(all_orders, key=lambda x: x.get('created_at', ''), reverse=True)
    return all_orders[:limit]

def get_order_statistics():
    """Get order statistics"""
    db = load_db()
    stats = {
        'total_orders': 0,
        'unpaid': 0,
        'paid': 0,
        'cancelled': 0,
        'expired': 0,
        'total_revenue': 0.0
    }
    
    for order in db.get('orders', {}).values():
        stats['total_orders'] += 1
        status = order.get('status', 'unknown')
        
        if status == 'unpaid':
            stats['unpaid'] += 1
        elif status == 'paid':
            stats['paid'] += 1
            price = order.get('price')
            if price:
                try:
                    stats['total_revenue'] += float(price)
                except (ValueError, TypeError):
                    pass
        elif status == 'cancelled':
            stats['cancelled'] += 1
        elif status == 'expired':
            stats['expired'] += 1
    
    return stats
