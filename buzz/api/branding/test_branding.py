import io
from typing import ClassVar
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from PIL import Image

from buzz.api.branding import app_tile_logo, get_branding, update_branding
from buzz.api.branding.exceptions import CannotEditBranding
from buzz.api.branding.services import TILE_FALLBACK
from buzz.emails import email_brand
from buzz.events.og_image import LOGO_BOX, WORDMARK_SIZE, EventOgImage, brand_logo
from buzz.www.site_header import DEFAULT_FAVICON, SiteHeader

BLANK = {
	"brand_name": None,
	"app_logo": None,
	"app_logo_dark": None,
	"app_icon": None,
	"favicon": None,
	"show_brand_name": False,
}


class BrandingTestCase(IntegrationTestCase):
	def setUp(self):
		# The site may install an app that sets a default brand, which these tests set for themselves
		self.enterContext(patch("buzz.brand.hooked", return_value=frappe._dict()))
		# Keeps the site's own branding out of every assertion; the rollback restores it
		for field, empty in BLANK.items():
			frappe.db.set_single_value("Buzz Settings", field, empty)
		frappe.clear_document_cache("Buzz Settings", "Buzz Settings")

	def update(self, **values):
		return update_branding(**{**BLANK, **values})

	def stored(self, field: str):
		return frappe.db.get_single_value("Buzz Settings", field)

	def upload(self, name: str, content: bytes) -> str:
		file = frappe.get_doc(
			{"doctype": "File", "file_name": name, "is_private": 0, "content": content}
		).insert(ignore_permissions=True)
		return file.file_url

	def png(self, size: tuple[int, int]) -> bytes:
		output = io.BytesIO()
		Image.new("RGBA", size, (200, 30, 30, 255)).save(output, "PNG")
		return output.getvalue()


class TestBrandingApi(BrandingTestCase):
	def test_reads_what_is_set_and_the_name_it_falls_back_to(self):
		frappe.db.set_single_value("Buzz Settings", "brand_name", "Acme Events")
		branding = get_branding()
		self.assertEqual(branding.brand_name, "Acme Events")
		self.assertIsNone(branding.favicon)
		self.assertTrue(branding.default_name)

	def test_saves_every_field_and_trims_the_name(self):
		self.update(
			brand_name="  Acme Events  ",
			app_logo="/files/light.png",
			app_logo_dark="/files/dark.png",
			app_icon="/files/icon.png",
			favicon="/files/fav.png",
		)
		self.assertEqual(self.stored("brand_name"), "Acme Events")
		self.assertEqual(self.stored("app_logo_dark"), "/files/dark.png")
		self.assertEqual(self.stored("app_icon"), "/files/icon.png")
		self.assertEqual(self.stored("favicon"), "/files/fav.png")

	def test_empty_values_clear_the_settings(self):
		self.update(brand_name="Acme", favicon="/files/fav.png")
		self.update(brand_name="  ", favicon="")
		self.assertFalse(self.stored("brand_name"))
		self.assertFalse(self.stored("favicon"))

	def test_a_light_logo_needs_the_dark_one(self):
		with self.assertRaises(frappe.ValidationError):
			self.update(app_logo="/files/light.png")
		self.assertFalse(self.stored("app_logo"))

	def test_only_a_system_manager_may_read_or_change_it(self):
		with self.set_user("Guest"):
			with self.assertRaises(CannotEditBranding):
				get_branding()
			with self.assertRaises(CannotEditBranding):
				self.update(brand_name="Mine")
		self.assertFalse(self.stored("brand_name"))


class TestBrandingReachesThePages(BrandingTestCase):
	def test_name_and_favicon_follow_the_settings(self):
		self.update(brand_name="Acme Events", favicon="/files/fav.png")
		brand = SiteHeader().brand()
		self.assertEqual((brand["name"], brand["favicon"]), ("Acme Events", "/files/fav.png"))
		self.assertEqual(SiteHeader().as_context()["favicon"], "/files/fav.png")

	def test_the_brand_says_whether_a_name_is_set(self):
		self.assertFalse(SiteHeader().brand()["is_named"])
		self.update(brand_name="Acme Events")
		self.assertTrue(SiteHeader().brand()["is_named"])

	def test_the_name_shows_beside_the_logo_only_when_asked(self):
		self.update(brand_name="Acme Events")
		self.assertFalse(SiteHeader().brand()["show_name"])
		self.update(brand_name="Acme Events", show_brand_name=True)
		self.assertTrue(SiteHeader().brand()["show_name"])
		self.assertTrue(get_branding().show_brand_name)

	def test_a_ticked_box_without_a_name_shows_nothing(self):
		self.update(show_brand_name=True)
		self.assertFalse(SiteHeader().brand()["show_name"])

	def test_without_settings_the_website_favicon_then_the_buzz_default_apply(self):
		self.set_website_favicon(None)
		self.assertEqual(SiteHeader().favicon(), DEFAULT_FAVICON)
		self.set_website_favicon("/files/site.ico")
		self.assertEqual(SiteHeader().favicon(), "/files/site.ico")

	def set_website_favicon(self, url: str | None):
		frappe.db.set_single_value("Website Settings", "favicon", url)
		frappe.clear_document_cache("Website Settings", "Website Settings")

	def test_apps_screen_tile_prefers_the_icon_then_the_logo_then_buzz(self):
		self.assertEqual(self.tile(), TILE_FALLBACK)
		self.update(app_logo="/files/light.png", app_logo_dark="/files/dark.png")
		self.assertEqual(self.tile(), "/files/light.png")
		self.update(app_logo="/files/light.png", app_logo_dark="/files/dark.png", app_icon="/files/icon.png")
		self.assertEqual(self.tile(), "/files/icon.png")

	def tile(self) -> str:
		app_tile_logo()
		self.assertEqual(frappe.local.response["type"], "redirect")
		return frappe.local.response["location"]


class TestShareImageLogo(BrandingTestCase):
	def share_image(self, logo_url: str | None) -> EventOgImage:
		# The mark needs only the colours and the logo, not an event
		image = object.__new__(EventOgImage)
		image.colours = {"ink-title": "#111111"}
		image.logo_url = logo_url
		return image

	def test_without_a_logo_it_draws_the_buzz_wordmark(self):
		self.assertEqual(self.share_image(None).brand_mark().size, WORDMARK_SIZE)

	def test_a_configured_logo_is_scaled_into_the_box(self):
		url = self.upload("wide-logo.png", self.png((800, 100)))
		mark = self.share_image(url).brand_mark()
		self.assertEqual(mark.width, LOGO_BOX[0])
		self.assertLessEqual(mark.height, LOGO_BOX[1])

	def test_a_logo_that_cannot_be_drawn_leaves_the_wordmark(self):
		url = self.upload("logo.svg", b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>')
		self.assertEqual(self.share_image(url).brand_mark().size, WORDMARK_SIZE)

	def test_the_dark_logo_goes_with_a_dark_theme(self):
		self.update(app_logo="/files/light.png", app_logo_dark="/files/dark.png")
		self.assertEqual(brand_logo("light"), "/files/light.png")
		self.assertEqual(brand_logo("dark"), "/files/dark.png")
		self.assertIsNone(self.logo_of_blank_site())

	def logo_of_blank_site(self):
		self.update()
		return brand_logo("light")


class TestAppDefaults(BrandingTestCase):
	DEFAULTS: ClassVar[dict[str, str]] = {
		"name": "Acme",
		"logo": "/assets/acme/light.png",
		"logo_dark": "/assets/acme/dark.png",
		"icon": "/assets/acme/mark.png",
		"favicon": "/assets/acme/fav.png",
	}

	def setUp(self):
		super().setUp()
		self.enterContext(patch("buzz.brand.hooked", return_value=frappe._dict(self.DEFAULTS)))
		for field in ("favicon", "banner_image", "app_logo"):
			frappe.db.set_single_value("Website Settings", field, None)
		frappe.clear_document_cache("Website Settings", "Website Settings")

	def test_an_empty_brand_falls_back_to_the_apps_defaults(self):
		brand = SiteHeader().brand()
		self.assertEqual(
			(brand["logo"], brand["logo_dark"], brand["icon"], brand["favicon"], brand["name"]),
			(
				"/assets/acme/light.png",
				"/assets/acme/dark.png",
				"/assets/acme/mark.png",
				"/assets/acme/fav.png",
				"Acme",
			),
		)
		self.assertEqual((brand["is_default"], brand["is_named"], brand["show_name"]), (False, True, False))

	def test_buzz_settings_beat_the_defaults_and_the_logos_stay_a_pair(self):
		self.update(
			brand_name="Mine", app_logo="/files/a.png", app_logo_dark="/files/b.png", favicon="/files/f.png"
		)
		brand = SiteHeader().brand()
		self.assertEqual(
			(brand["logo"], brand["logo_dark"], brand["favicon"]),
			("/files/a.png", "/files/b.png", "/files/f.png"),
		)
		self.assertEqual((brand["name"], brand["icon"]), ("Mine", "/assets/acme/mark.png"))

	def test_the_branding_page_is_told_what_the_defaults_are(self):
		branding = get_branding()
		self.assertEqual(branding.default_name, "Acme")
		self.assertEqual(
			(
				branding.default_logo,
				branding.default_logo_dark,
				branding.default_icon,
				branding.default_favicon,
			),
			(
				"/assets/acme/light.png",
				"/assets/acme/dark.png",
				"/assets/acme/mark.png",
				"/assets/acme/fav.png",
			),
		)
		self.assertIsNone(branding.brand_name)

	def test_the_apps_tile_and_share_image_and_emails_follow_the_defaults(self):
		app_tile_logo()
		self.assertEqual(frappe.local.response["location"], "/assets/acme/mark.png")
		self.assertEqual(
			(brand_logo("light"), brand_logo("dark")), ("/assets/acme/light.png", "/assets/acme/dark.png")
		)
		mail = email_brand()
		self.assertTrue(mail.logo.endswith("/assets/acme/light.png"))
		self.assertEqual(mail.name, "Acme")

	def test_a_logo_shipped_in_an_app_can_be_drawn(self):
		mark = self.share_image_of("/assets/buzz/images/buzz-logo.png").configured_logo()
		self.assertIsNotNone(mark)
		self.assertLessEqual(mark.width, LOGO_BOX[0])
		self.assertLessEqual(mark.height, LOGO_BOX[1])

	def test_a_path_that_leaves_the_apps_folder_is_not_read(self):
		self.assertIsNone(self.share_image_of("/assets/buzz/../../../../etc/hostname").configured_logo())

	def share_image_of(self, logo_url: str) -> EventOgImage:
		image = object.__new__(EventOgImage)
		image.colours = {"ink-title": "#111111"}
		image.logo_url = logo_url
		return image
