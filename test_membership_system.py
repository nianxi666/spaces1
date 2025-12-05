#!/usr/bin/env python3
"""
Simple test script to verify the membership system functions work correctly.
Run this from the project root: python3 test_membership_system.py
"""

import os
import sys
from datetime import datetime, timedelta
from flask import Flask
import project.config as config

# Create a Flask app context
app = Flask(__name__)
app.config.from_object(config)
app.instance_path = os.path.join(os.path.dirname(__file__), 'instance')
app.root_path = os.path.join(os.path.dirname(__file__), 'project')

def test_membership_system():
    """Test the membership system functions"""
    
    print("=" * 60)
    print("MEMBERSHIP SYSTEM TEST")
    print("=" * 60)
    
    with app.app_context():
        from project.database import load_db, save_db
        from project.membership import (
            is_membership_enabled,
            is_user_member,
            get_user_membership_status,
            set_user_membership,
            revoke_user_membership
        )
        
        # Load database
        db = load_db()
        print("\n✓ Database loaded successfully")
        
        # Check membership settings
        membership_settings = db.get('membership_settings', {})
        print(f"\n📋 Current Membership Settings:")
        print(f"   Enabled: {membership_settings.get('enabled')}")
        print(f"   Price: ${membership_settings.get('price_usd')}/month")
        print(f"   Duration: {membership_settings.get('duration_days')} days")
        print(f"   Payhip API Key: {'✓ Set' if membership_settings.get('payhip_api_key') else '✗ Not set'}")
        print(f"   Payhip Product ID: {'✓ Set' if membership_settings.get('payhip_product_id') else '✗ Not set'}")
        
        # Test with a test user
        test_username = 'test_user_membership'
        
        # Create test user if not exists
        if test_username not in db.get('users', {}):
            db['users'][test_username] = {
                'password_hash': 'hashed_password',
                'api_key': 'test_api_key_12345',
                'is_member': False,
                'member_expiry_date': None,
                'payment_history': []
            }
            save_db(db)
            print(f"\n✓ Created test user: {test_username}")
        
        # Test get_user_membership_status
        status = get_user_membership_status(test_username)
        print(f"\n📊 Initial status for {test_username}:")
        print(f"   Is Member: {status['is_member']}")
        print(f"   Days Remaining: {status['days_remaining']}")
        print(f"   Expired: {status['expired']}")
        
        # Test set_user_membership
        set_user_membership(test_username, 30)
        print(f"\n✓ Set {test_username} as member for 30 days")
        
        # Verify membership was set
        status = get_user_membership_status(test_username)
        print(f"\n📊 After setting membership:")
        print(f"   Is Member: {status['is_member']}")
        print(f"   Days Remaining: {status['days_remaining']}")
        print(f"   Expiry Date: {status['expiry_date']}")
        
        # Test is_user_member
        is_member = is_user_member(test_username)
        print(f"\n✓ is_user_member('{test_username}'): {is_member}")
        
        # Test revoke_user_membership
        revoke_user_membership(test_username)
        print(f"\n✓ Revoked membership for {test_username}")
        
        # Verify membership was revoked
        status = get_user_membership_status(test_username)
        print(f"\n📊 After revoking membership:")
        print(f"   Is Member: {status['is_member']}")
        
        # Check user payment history
        db = load_db()
        user = db.get('users', {}).get(test_username, {})
        print(f"\n💳 Payment History for {test_username}:")
        if user.get('payment_history'):
            for i, payment in enumerate(user['payment_history'], 1):
                print(f"   {i}. {payment.get('type')} - {payment.get('duration_days')} days - {payment.get('timestamp')[:10]}")
        else:
            print(f"   (empty)")
        
        # Test with expired membership
        print(f"\n🧪 Testing with expired membership:")
        # Set expiry to yesterday
        yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
        db['users'][test_username]['member_expiry_date'] = yesterday
        db['users'][test_username]['is_member'] = True
        save_db(db)
        
        status = get_user_membership_status(test_username)
        is_member = is_user_member(test_username)
        print(f"   Expiry Date: {yesterday[:10]}")
        print(f"   Is Member (should be False): {is_member}")
        print(f"   Status.is_member (should be False): {status['is_member']}")
        print(f"   Status.expired (should be True): {status['expired']}")
        
        # Cleanup
        print(f"\n🧹 Cleaning up test user...")
        revoke_user_membership(test_username)
        db = load_db()
        del db['users'][test_username]
        save_db(db)
        print(f"✓ Deleted test user: {test_username}")
        
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)

if __name__ == '__main__':
    try:
        test_membership_system()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
