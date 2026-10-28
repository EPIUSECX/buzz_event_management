import frappe
from frappe import _
from frappe.utils import flt
from pydantic import AliasPath, BaseModel, ConfigDict, Field

from buzz.ticketing.doctype.event_booking_refund.event_booking_refund import record_gateway_refund


class RefundNotification(BaseModel):
	"""The refund a Razorpay `refund.processed` or `refund.failed` webhook carries.

	The fields sit at `payload.refund.entity` in the webhook body, and every one
	of them is mandatory: bma_integrations hands us refund events only, and a
	refund event without them is broken rather than uninteresting.
	"""

	model_config = ConfigDict(extra="ignore")

	refund_id: str = Field(validation_alias=AliasPath("payload", "refund", "entity", "id"))
	payment_id: str = Field(validation_alias=AliasPath("payload", "refund", "entity", "payment_id"))
	status: str = Field(validation_alias=AliasPath("payload", "refund", "entity", "status"))
	amount_in_minor_unit: int = Field(validation_alias=AliasPath("payload", "refund", "entity", "amount"))

	@property
	def amount(self) -> float:
		"""What the gateway refunded, in the major unit the booking is priced in."""
		return flt(self.amount_in_minor_unit) / 100


def get_payment_gateways_for_event(event: str) -> list[str]:
	"""Get the event's own payment gateways, or the site default when it has none."""
	gateways = frappe.get_all(
		"Event Payment Gateway",
		filters={"parent": event, "parenttype": "Buzz Event"},
		pluck="payment_gateway",
	)
	default = frappe.db.get_single_value("Buzz Settings", "default_payment_gateway")
	return gateways or ([default] if default else [])


def resolve_payment_gateway(event: str, payment_gateway: str | None) -> str:
	"""The gateway the client picked, as long as the event takes payments through it."""
	gateways = get_payment_gateways_for_event(event)
	if not gateways:
		frappe.throw(_("No payment gateway configured for this event"))
	if payment_gateway and payment_gateway not in gateways:
		frappe.throw(_("{0} is not a payment gateway for this event").format(payment_gateway))
	return payment_gateway or gateways[0]


def get_controller(payment_gateway):
	from bma_integrations.payments.utils import get_payment_gateway_controller

	return get_payment_gateway_controller(payment_gateway)


def gateway_settings(payment_gateway: str) -> str | None:
	"""The settings doctype behind a gateway, e.g. "Payfast Settings" for "Payfast-Main"."""
	return frappe.db.get_value("Payment Gateway", payment_gateway, "gateway_settings")


def settles_through_checkout(payment_gateway: str) -> bool:
	"""Whether the gateway reports the outcome against the checkout bma_integrations logs.

	PayFast, Peach, Paystack, Bob Pay and Stitch do. The payment id is then the
	checkout's own id, and refunds go through `refund_document`.
	"""
	from bma_integrations.payments.references import CHECKOUT_GATEWAYS

	return gateway_settings(payment_gateway) in CHECKOUT_GATEWAYS


def get_payment_link_for_booking(
	booking_id: str, redirect_to: str = "/events", payment_gateway: str | None = None
) -> str:
	booking_doc = frappe.get_cached_doc("Event Booking", booking_id)
	event_title = frappe.get_cached_value("Buzz Event", booking_doc.event, "title")
	payment_gateway = resolve_payment_gateway(booking_doc.event, payment_gateway)
	return get_payment_link(
		"Event Booking",
		booking_id,
		booking_doc.total_amount,
		booking_doc.currency,
		payment_gateway,
		redirect_to=redirect_to,
		title=f"Payment for {event_title}",
	)


def get_payment_link_for_sponsorship(
	sponsorship_enquiry: str,
	sponsorship_tier: str,
	redirect_to: str = "/events",
	payment_gateway: str | None = None,
	currency: str | None = None,
) -> str:
	tier_doc = frappe.get_cached_doc("Sponsorship Tier", sponsorship_tier)
	if not tier_doc.enabled:
		frappe.throw(_("This sponsorship tier is no longer available."))
	payment_gateway = resolve_payment_gateway(tier_doc.event, payment_gateway)
	event_title = frappe.get_cached_value("Buzz Event", tier_doc.event, "title")
	price = tier_doc.price_for(currency)
	frappe.db.set_value(
		"Sponsorship Enquiry", sponsorship_enquiry, "tier", sponsorship_tier
	)  # TODO: rethink later

	return get_payment_link(
		"Sponsorship Enquiry",
		sponsorship_enquiry,
		price.price,
		price.currency,
		payment_gateway,
		redirect_to,
		f"Payment for {tier_doc.title} Sponsorship at {event_title}",
	)


def get_payment_link(
	reference_doctype: str,
	reference_docname: str,
	amount: float,
	currency: str,
	payment_gateway: str,
	redirect_to: str = "/events",
	title: str | None = None,
) -> str:
	controller = get_controller(payment_gateway)
	# Not every gateway controller implements this check.
	if hasattr(controller, "validate_transaction_currency"):
		controller.validate_transaction_currency(currency)
	payment = record_payment(reference_doctype, reference_docname, amount, currency, payment_gateway)
	payer = payer_of(reference_doctype, reference_docname)

	payment_details = {
		"amount": amount,
		"title": title or f"Payment for {reference_doctype}: {reference_docname}",
		"description": f"{payer.name}'s payment for {reference_doctype} (#{reference_docname})",
		"reference_doctype": reference_doctype,
		"reference_docname": reference_docname,
		"payer_email": payer.email,
		"payer_name": payer.name,
		"payer_phone": payer.phone,
		"currency": currency,
		"payment_gateway": payment_gateway,
		"redirect_to": redirect_to,
		"payment": payment.name,
	}
	if payment_gateway == "Razorpay" or payment_gateway == "Paymob":
		order = controller.create_order(**payment_details)
		payment_details.update({"order_id": order.get("id")})

	url = controller.get_payment_url(**payment_details)

	return url


def payer_of(reference_doctype: str, reference_docname: str) -> frappe._dict:
	"""Who is paying, as the document records them.

	The session user is often Administrator or a guest account with no address a gateway can use,
	while the buyer on the booking gave a real name, email and number.
	"""
	name = email = phone = None
	if reference_doctype == "Event Booking":
		name, email, phone = frappe.db.get_value(
			"Event Booking", reference_docname, ["buyer_name", "buyer_email", "buyer_phone"]
		)
	elif reference_doctype == "Sponsorship Enquiry":
		name, email, phone = frappe.db.get_value(
			"Sponsorship Enquiry", reference_docname, ["company_name", "contact_email", "phone"]
		)
	user = frappe.session.user
	return frappe._dict(
		name=name or frappe.get_cached_value("User", user, "full_name"),
		email=email or (user if "@" in user else None),
		phone=phone,
	)


def record_payment(
	reference_doctype: str,
	reference_docname: str,
	amount: float,
	currency: str,
	payment_gateway: str | None = None,
):
	payment_doc = frappe.new_doc("Event Payment")
	payment_doc.update(
		{
			"user": frappe.session.user,
			"amount": amount,
			"currency": currency,
			"reference_doctype": reference_doctype,
			"reference_docname": reference_docname,
			"payment_gateway": payment_gateway,
		}
	)
	payment_doc.save(ignore_permissions=True)
	return payment_doc


def mark_payment_as_received(reference_doctype: str, reference_docname: str):
	if frappe.in_test:
		return

	request = frappe.get_all(
		"Integration Request",
		{
			"reference_doctype": reference_doctype,
			"reference_docname": reference_docname,
		},
		fields=["name", "request_id", "data"],
		order_by="creation desc",
		limit=1,
	)

	if len(request):
		data = frappe.parse_json(request[0].data)

		if data.get("gateway") and not data.get("payment"):
			# A checkout bma_integrations logged: it carries the gateway's own id.
			mark_checkout_as_received(reference_doctype, reference_docname, request[0].request_id)
			return

		payment_gateway = data.get("payment_gateway")
		if payment_gateway == "Razorpay":
			payment_id = "razorpay_payment_id"

		elif payment_gateway == "Paymob":
			payment_id = "paymob_payment_id"

		elif payment_gateway == "PayPal":
			payment_id = "transaction_id"

		elif "Stripe" in payment_gateway:
			payment_id = "stripe_token_id"
		else:
			payment_id = "order_id"

		frappe.db.set_value(
			"Event Payment",
			data.payment,
			{
				"payment_received": 1,
				"payment_id": data.get(payment_id),
				"order_id": data.get("order_id"),
			},
		)

		frappe.db.commit()  # nosemgrep: frappe-manual-commit


def mark_checkout_as_received(reference_doctype: str, reference_docname: str, payment_id: str) -> None:
	"""Mark the latest payment for the document received, with the id of the checkout that paid it."""
	payment = frappe.get_all(
		"Event Payment",
		{"reference_doctype": reference_doctype, "reference_docname": reference_docname},
		order_by="creation desc",
		pluck="name",
		limit=1,
	)
	if payment:
		frappe.db.set_value(
			"Event Payment",
			payment[0],
			{"payment_received": 1, "payment_id": payment_id, "order_id": payment_id},
		)


def handle_refund_notification(doctype: str, docname: str) -> None:
	"""Apply a gateway refund webhook to the booking whose payment it belongs to."""
	# Returns nothing on purpose: `call_hook_method` stops at the first handler
	# that returns a value.
	payload = frappe.parse_json(frappe.db.get_value(doctype, docname, "data"))
	notification = RefundNotification.model_validate(payload)

	payment = frappe.db.get_value(
		"Event Payment",
		{"payment_id": notification.payment_id},
		["name", "reference_doctype", "reference_docname"],
		as_dict=True,
	)

	if not payment or payment.reference_doctype != "Event Booking":
		return

	# The same event arrives more than once, so the refund is keyed on its id.
	record_gateway_refund(
		booking=payment.reference_docname,
		payment=payment.name,
		refund_id=notification.refund_id,
		status=notification.status,
		amount=notification.amount,
	)

	frappe.db.set_value(
		doctype,
		docname,
		{"reference_doctype": "Event Booking", "reference_docname": payment.reference_docname},
		update_modified=False,
	)


# TODO: use it later!
def save_address(address):
	filters = {"email_id": frappe.session.user}
	exists = frappe.db.exists("Address", filters)
	if exists:
		address_doc = frappe.get_last_doc("Address", filters=filters)
	else:
		address_doc = frappe.new_doc("Address")

	address_doc.update(address)
	address_doc.update(
		{
			"address_title": frappe.db.get_value("User", frappe.session.user, "full_name"),
			"address_type": "Billing",
			"is_primary_address": 1,
			"email_id": frappe.session.user,
		}
	)
	address_doc.save(ignore_permissions=True)
	return address_doc.name
