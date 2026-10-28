import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from buzz.payments import mark_payment_as_received


class TestMarkPaymentAsReceived(IntegrationTestCase):
	def test_a_checkout_logged_by_a_gateway_is_found_and_marked(self):
		frappe.get_doc(
			{
				"doctype": "Integration Request",
				"integration_request_service": "Bob Pay",
				"request_description": "Bob Pay Checkout",
				"request_id": "B-MARK-1-abcd1234",
				"status": "Completed",
				"reference_doctype": "Event Booking",
				"reference_docname": "B-MARK-1",
				"data": json.dumps({"gateway": "Bob Pay Test"}),
			}
		).insert(ignore_permissions=True, ignore_links=True)

		with (
			patch("frappe.in_test", False),
			patch("buzz.payments.mark_checkout_as_received") as mark,
		):
			mark_payment_as_received("Event Booking", "B-MARK-1")

		mark.assert_called_once_with("Event Booking", "B-MARK-1", "B-MARK-1-abcd1234")
