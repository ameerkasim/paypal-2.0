import os
import tempfile
import unittest
from unittest.mock import patch

import app as payai

class PayAITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.NamedTemporaryFile(delete=False)
        self.temp.close()
        payai.DATABASE = self.temp.name
        payai.init_db()
        self.client = payai.app.test_client()

    def tearDown(self):
        os.unlink(self.temp.name)

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["ok"])

    @patch("app.generate_ai_quote", return_value=("Test quotation", "fallback"))
    def test_create_quote(self, _mock):
        response = self.client.post("/api/quotes", json={
            "customer_name": "Test User",
            "customer_email": "test@example.com",
            "description": "Website design",
            "amount": "25.00"
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["amount"], "25.00")
        self.assertEqual(response.json["status"], "PENDING")

    def test_reject_invalid_amount(self):
        response = self.client.post("/api/quotes", json={
            "customer_name": "Test User",
            "customer_email": "test@example.com",
            "description": "Service",
            "amount": "-5"
        })
        self.assertEqual(response.status_code, 400)

    def test_missing_invoice_cannot_create_order(self):
        response = self.client.post("/api/paypal/create-order", json={"invoice_id": "NOT-REAL"})
        self.assertEqual(response.status_code, 404)

if __name__ == "__main__":
    unittest.main()
