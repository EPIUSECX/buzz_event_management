from frappe import _lt

from buzz.api.exceptions import BuzzAPIError


class CannotEditBranding(BuzzAPIError):
	http_status_code = 403
	title = _lt("Not Allowed")
	message = _lt("Only a System Manager can change the branding.")
