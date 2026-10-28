import frappe

from buzz.api.branding.exceptions import CannotEditBranding
from buzz.api.branding.schemas import BrandingSettings
from buzz.www.site_header import default_brand_name

TILE_FALLBACK = "/assets/buzz/images/buzz-logo-rounded.png"
FIELDS = ("brand_name", "app_logo", "app_logo_dark", "app_icon", "favicon")


def can_manage() -> bool:
	return "System Manager" in frappe.get_roles()


def require_manager():
	"""Buzz Settings is a System Manager doctype, so this guard is the authorization for the save."""
	if not can_manage():
		CannotEditBranding.throw()


def configured_branding() -> BrandingSettings:
	settings = frappe.get_doc("Buzz Settings")
	return BrandingSettings(
		**{field: settings.get(field) or None for field in FIELDS}, default_name=default_brand_name()
	)


def save_branding(**values: str | None):
	settings = frappe.get_doc("Buzz Settings")
	for field in FIELDS:
		settings.set(field, (values[field] or "").strip() or None)
	# The doctype refuses a light logo without a dark one
	settings.save(ignore_permissions=True)


def tile_logo() -> str:
	"""The square mark suits a tile best, then the logo, then the Buzz mark."""
	settings = frappe.get_cached_doc("Buzz Settings")
	return settings.app_icon or settings.app_logo or TILE_FALLBACK
