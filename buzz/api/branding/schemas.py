from buzz.api.schemas import APIResponse


class BrandingSettings(APIResponse):
	"""What is set, not what is shown: an empty value falls back to the Buzz default."""

	brand_name: str | None
	app_logo: str | None
	app_logo_dark: str | None
	app_icon: str | None
	favicon: str | None
	# What an empty name falls back to.
	default_name: str
