from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from buzz.payments import get_payment_link, payer_of

BUYER = ("Jane Doe", "jane@example.com", "+27-735997905")


class TestPayerOf(IntegrationTestCase):
	def test_a_booking_names_its_buyer(self):
		with patch("frappe.db.get_value", return_value=BUYER):
			payer = payer_of("Event Booking", "B1")
		self.assertEqual((payer.name, payer.email, payer.phone), BUYER)

	def test_an_enquiry_names_its_company_contact(self):
		with patch("frappe.db.get_value", return_value=("Acme", "hello@acme.test", "+27-821234567")):
			payer = payer_of("Sponsorship Enquiry", "E1")
		self.assertEqual((payer.name, payer.email, payer.phone), ("Acme", "hello@acme.test", "+27-821234567"))

	def test_without_a_buyer_email_the_session_user_stands_in_only_if_it_is_an_address(self):
		with patch("frappe.db.get_value", return_value=("Jane Doe", None, None)):
			with self.set_user("Administrator"):
				self.assertIsNone(payer_of("Event Booking", "B1").email)
			with self.set_user("test@example.com"):
				self.assertEqual(payer_of("Event Booking", "B1").email, "test@example.com")


class TestPaymentLinkPayer(IntegrationTestCase):
	def test_the_gateway_gets_the_buyer_not_the_session_user(self):
		controller = MagicMock()
		controller.get_payment_url.return_value = "https://pay.example/1"
		with (
			patch("buzz.payments.get_controller", return_value=controller),
			patch("buzz.payments.record_payment", return_value=frappe._dict(name="EVP-1")),
			patch("frappe.db.get_value", return_value=BUYER),
			self.set_user("Administrator"),
		):
			url = get_payment_link("Event Booking", "B1", 100, "ZAR", "Bob Pay-Bob Pay Test", title="Run")

		self.assertEqual(url, "https://pay.example/1")
		sent = controller.get_payment_url.call_args.kwargs
		self.assertEqual((sent["payer_name"], sent["payer_email"], sent["payer_phone"]), BUYER)
		self.assertIn("Jane Doe", sent["description"])
