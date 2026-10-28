import frappe

from buzz.api.branding import services
from buzz.api.branding.schemas import BrandingSettings


@frappe.whitelist()
def get_branding() -> BrandingSettings:
	services.require_manager()
	return services.configured_branding()


@frappe.whitelist(methods=["POST"])
def update_branding(
	brand_name: str | None,
	app_logo: str | None,
	app_logo_dark: str | None,
	app_icon: str | None,
	favicon: str | None,
	show_brand_name: bool = False,
) -> BrandingSettings:
	services.require_manager()
	services.save_branding(
		brand_name=brand_name,
		app_logo=app_logo,
		app_logo_dark=app_logo_dark,
		app_icon=app_icon,
		favicon=favicon,
		show_brand_name=show_brand_name,
	)
	return services.configured_branding()


# Desk reads the apps-screen logo from a hook, which cannot hold a setting, so the hook points here.
@frappe.whitelist(allow_guest=True)  # nosemgrep: guest-whitelisted-method
def app_tile_logo():
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = services.tile_logo()
