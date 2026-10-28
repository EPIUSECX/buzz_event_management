from buzz.api.schemas import APIResponse


class BrandingSettings(APIResponse):
	"""What is set, not what is shown: an empty value falls back to the Buzz default."""

	brand_name: str | None
	app_logo: str | None
	app_logo_dark: str | None
	app_icon: str | None
	favicon: str | None
	show_brand_name: bool
	# What an empty name falls back to.
	default_name: str
	# What an empty logo, icon or favicon falls back to, when an app installed beside Buzz sets one.
	default_logo: str | None
	default_logo_dark: str | None
	default_icon: str | None
	default_favicon: str | None
