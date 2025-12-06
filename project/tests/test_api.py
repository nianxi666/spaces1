import unittest
import json
from unittest.mock import patch, MagicMock
from flask import Flask
from project.api import api_bp
from project import create_app

class TestPayhipWebhook(unittest.TestCase):
    def setUp(self):
        self.app = create_app({'TESTING': True, 'SERVER_NAME': 'localhost'})
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    @patch('project.api.load_db')
    @patch('project.api.save_db')
    def test_webhook_success(self, mock_save, mock_load):
        # Setup mock DB
        mock_db = {
            'users': {'testuser': {'membership_expiry': '2023-01-01'}},
            'payment_settings': {'webhook_secret': 'secret123'},
            'orders': []
        }
        mock_load.return_value = mock_db

        # Payload simulating Payhip
        payload = {
            'id': 'tx_123',
            'email': 'test@example.com',
            'price': '5.00',
            'currency': 'USD',
            'checkout_custom_variables': json.dumps({'username': 'testuser'})
        }

        # Make request
        response = self.client.post(
            '/api/payment/payhip/webhook?key=secret123',
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_save.called)

        # Verify order added
        self.assertEqual(len(mock_db['orders']), 1)
        self.assertEqual(mock_db['orders'][0]['username'], 'testuser')
        self.assertEqual(mock_db['orders'][0]['status'], 'paid')

        # Verify user upgraded
        # Expiry should be roughly now + 30 days. We won't check exact time but it should be > 2023-01-01
        self.assertNotEqual(mock_db['users']['testuser']['membership_expiry'], '2023-01-01')

    @patch('project.api.load_db')
    def test_webhook_unauthorized(self, mock_load):
        mock_db = {
            'payment_settings': {'webhook_secret': 'secret123'}
        }
        mock_load.return_value = mock_db

        response = self.client.post('/api/payment/payhip/webhook?key=wrongsecret')
        self.assertEqual(response.status_code, 401)

    @patch('project.api.load_db')
    def test_webhook_missing_username(self, mock_load):
        mock_db = {
            'users': {},
            'payment_settings': {'webhook_secret': 'secret123'}
        }
        mock_load.return_value = mock_db

        payload = {
            'id': 'tx_123',
            'checkout_custom_variables': json.dumps({}) # No username
        }

        response = self.client.post(
            '/api/payment/payhip/webhook?key=secret123',
            data=json.dumps(payload),
            content_type='application/json'
        )

        # Should return 200 (to satisfy Payhip) but log error
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Username not found', response.data)

if __name__ == '__main__':
    unittest.main()
