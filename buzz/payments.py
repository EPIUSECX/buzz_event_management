import frappe
from frappe import _
from frappe.utils import cint, cstr, flt
from pydantic import AliasPath, BaseModel, ConfigDict, Field

from buzz.ticketing.doctype.event_booking_refund.event_booking_refund import record_gateway_refund

GATEWAY_PAYMENT_ID_FIELDS = {
	"Razorpay": "razorpay_payment_id",
	"Paymob": "paymob_payment_id",
	"PayPal": "transaction_id",
}


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


# An enquiry still open for its applicant to pay for.
PAYABLE_ENQUIRY_STATUSES = ("Approval Pending", "Payment Pending")


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
	# Read fresh: the status is what gates a second payment, and `db_set` leaves the cache stale.
	enquiry = frappe.db.get_value(
		"Sponsorship Enquiry", sponsorship_enquiry, ["event", "status"], as_dict=True
	)
	tier_doc = frappe.get_cached_doc("Sponsorship Tier", sponsorship_tier)
	if str(tier_doc.event) != str(enquiry.event):
		frappe.throw(_("This sponsorship tier is not offered for this event."))
	if enquiry.status not in PAYABLE_ENQUIRY_STATUSES:
		frappe.throw(_("This sponsorship enquiry is not open for payment."))
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
		payment.db_set("order_id", order.get("id"))

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
	request = latest_payment_request(reference_doctype, reference_docname)
	data = request.data

	if data.get("gateway") and not data.get("payment"):
		# A checkout bma_integrations logged: it carries the gateway's own id.
		mark_checkout_as_received(reference_doctype, reference_docname, request.request_id)
		return

	# The request data carries client-chosen values, so the server-made payment row decides.
	payment = frappe.get_last_doc(
		"Event Payment",
		filters={
			"reference_doctype": reference_doctype,
			"reference_docname": reference_docname,
			"payment_received": 0,
		},
	)
	payment_id = data.get(payment_id_field(payment.payment_gateway))
	if payment.payment_gateway == "Razorpay":
		verify_razorpay_payment(payment, payment_id)

	frappe.db.set_value(
		"Event Payment",
		payment.name,
		{
			"payment_received": 1,
			"payment_id": payment_id,
			"order_id": payment.order_id or data.get("order_id"),
		},
	)

	frappe.db.commit()  # nosemgrep: frappe-manual-commit


def latest_payment_request(reference_doctype: str, reference_docname: str) -> frappe._dict:
	"""The newest Integration Request logged for the document, with its data parsed."""
	filters = {"reference_doctype": reference_doctype, "reference_docname": reference_docname}
	request = frappe.db.get_value(
		"Integration Request", filters, ["request_id", "data"], order_by="creation desc", as_dict=True
	)
	if not request:
		frappe.throw(_("No payment request found for {0}").format(reference_docname))
	request.data = frappe.parse_json(request.data)
	return request


def payment_request_data(reference_doctype: str, reference_docname: str) -> dict:
	return latest_payment_request(reference_doctype, reference_docname).data


def payment_id_field(payment_gateway: str) -> str:
	if "Stripe" in payment_gateway:
		return "stripe_token_id"
	return GATEWAY_PAYMENT_ID_FIELDS.get(payment_gateway, "order_id")


def verify_razorpay_payment(payment, payment_id: str | None):
	"""An order takes one captured payment, so this row's own order cannot pay anything else."""
	if not payment_id:
		frappe.throw(_("Payment id is missing"))

	gateway_payment = get_controller("Razorpay").fetch_payment(payment_id)
	if not payment.order_id or gateway_payment.get("order_id") != payment.order_id:
		frappe.throw(_("This payment is not for this order"))

	# The payments app truncates an order's amount to paise, so it can sit one below the total.
	if abs(cint(gateway_payment.get("amount")) - flt(payment.amount) * 100) > 1:
		frappe.throw(_("Paid amount does not match the amount due"))

	if cstr(gateway_payment.get("currency")).upper() != cstr(payment.currency).upper():
		frappe.throw(_("Paid currency does not match the currency due"))


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
