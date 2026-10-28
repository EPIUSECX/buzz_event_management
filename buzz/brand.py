"""The brand Buzz shows where Buzz Settings leaves a setting empty.

An app installed beside Buzz sets the defaults with a hook, so the Buzz fork stays neutral:

	buzz_brand_defaults = {
		"name": "Acme",
		"logo": "/assets/acme/images/logo-light.png",
		"logo_dark": "/assets/acme/images/logo-dark.png",
		"icon": "/assets/acme/images/mark.png",
		"favicon": "/assets/acme/images/favicon.png",
		"issues_url": "https://github.com/acme/buzz/issues/new",
	}

Every key is optional. Buzz Settings always wins, and the two logos only ever come as one pair.
"""

import frappe

ISSUES_URL = "https://github.com/bwhtech/buzz/issues/new"


def hooked() -> frappe._dict:
	values = frappe.get_hooks("buzz_brand_defaults") or {}
	return frappe._dict({key: items[-1] for key, items in values.items() if items})


def logos() -> tuple[str | None, str | None]:
	"""The light and the dark logo."""
	settings = frappe.get_cached_doc("Buzz Settings")
	if settings.app_logo:
		return settings.app_logo, settings.app_logo_dark
	defaults = hooked()
	return defaults.get("logo"), defaults.get("logo_dark")


def logo_for(scheme: str) -> str | None:
	light, dark = logos()
	return (dark if scheme == "dark" else light) or light or dark


def icon() -> str | None:
	return frappe.get_cached_doc("Buzz Settings").app_icon or hooked().get("icon")


def issues_url() -> str:
	"""Where the user menu sends Report an Issue."""
	return hooked().get("issues_url") or ISSUES_URL


def name() -> str | None:
	return frappe.get_cached_doc("Buzz Settings").brand_name or hooked().get("name")
