"""Bookings paid through a gateway that bma_integrations settles by checkout.

PayFast, Peach, Paystack, Bob Pay and Stitch report the outcome against the checkout
bma_integrations logged, so the payment id is that checkout's id, a refund goes through
`refund_document`, and a refund that settles later arrives through `on_payment_refund`.
"""

from unittest.mock import patch

import frappe

from buzz.payments import mark_checkout_as_received
from buzz.tests.base_test_cases import BookingRefundTestCase
from buzz.tests.factories import EventPaymentFactory, PaymentGatewayFactory

REFUND_DOCUMENT = "bma_integrations.payments.references.refund_document"


def peach_gateway() -> str:
	"""Only the settings doctype decides the route, so no Peach account is needed."""
	name = "Peach-Buzz Test"
	if not frappe.db.exists("Payment Gateway", name):
		PaymentGatewayFactory.create(gateway=name, gateway_settings="Peach Payments Settings")
	return name


class TestCheckoutRefunds(BookingRefundTestCase):
	def setUp(self):
		super().setUp()
		self.make_payment(peach_gateway())

	def log(self) -> str:
		return f"IR-{self._testMethodName}"

	def refund_through_checkout(self, amount: float, status: str = "Queued"):
		sent = {"refund": self.log(), "status": status, "amount": amount}
		with patch(REFUND_DOCUMENT, return_value=sent) as refund_document, patch("frappe.sendmail"):
			self.booking.refund(amount=amount)
		self.booking.reload()
		return refund_document

	def test_the_refund_is_sent_through_bma_integrations_for_this_booking(self):
		refund_document = self.refund_through_checkout(100)

		refund_document.assert_called_once_with(
			self.payment.payment_gateway, "Event Booking", self.booking.name, 100.0
		)
		[refund] = self.refunds()
		self.assertEqual((refund.refund_id, refund.status, refund.amount), (self.log(), "Initiated", 100.0))
		self.assertEqual(self.booking.refund_status, "Refund Initiated")

	def test_a_refund_the_gateway_settles_at_once_is_processed(self):
		self.refund_through_checkout(100, status="Completed")

		[refund] = self.refunds()
		self.assertEqual(refund.status, "Processed")
		self.assertEqual(self.booking.refunded_amount, 100)

	def test_a_refund_that_settles_later_is_recorded_when_it_is_reported(self):
		self.refund_through_checkout(100)

		with patch("frappe.sendmail"):
			self.booking.on_payment_refund(self.log(), "Completed", 100.0)

		[refund] = self.refunds()
		self.assertEqual(refund.status, "Processed")

	def test_a_failed_refund_is_recorded_as_failed(self):
		self.refund_through_checkout(100)

		self.booking.on_payment_refund(self.log(), "Failed", 100.0)

		[refund] = self.refunds()
		self.assertEqual(refund.status, "Failed")

	def test_there_is_nothing_to_sync(self):
		with self.assertRaisesRegex(frappe.ValidationError, "nothing to sync"):
			self.booking.sync_refunds()


class TestCheckoutReceipt(BookingRefundTestCase):
	def test_the_payment_takes_the_id_of_the_checkout_that_paid_it(self):
		payment = EventPaymentFactory.create(
			user=self.booking.user,
			amount=self.booking.total_amount,
			currency=self.booking.currency,
			reference_doctype="Event Booking",
			reference_docname=self.booking.name,
			payment_gateway=peach_gateway(),
		)

		mark_checkout_as_received("Event Booking", self.booking.name, "pay_checkout_1")

		payment.reload()
		self.assertEqual((payment.payment_received, payment.payment_id), (1, "pay_checkout_1"))
