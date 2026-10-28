const LOGO_DIRECTORY = "/assets/buzz/images/payment_gateways"

// Brand marks are drawn for one background, so each gateway ships a version per theme.
interface PaymentGatewayLogoFiles {
	light: string
	dark: string
}

const logoFiles = (name: string, extension = "svg"): PaymentGatewayLogoFiles => ({
	light: `${LOGO_DIRECTORY}/${name}.${extension}`,
	dark: `${LOGO_DIRECTORY}/${name}-dark.${extension}`,
})

// Keyed by the provider part of the gateway's name. The South African gateways come from
// bma_integrations, which names them "Payfast-<account>", "Peach-<account>" and so on. Their
// marks are rasters; the dark files of Bob Pay and PayFast sit on a white tile, as their ink is dark.
const LOGOS: Record<string, PaymentGatewayLogoFiles> = {
	Razorpay: logoFiles("razorpay"),
	Payfast: logoFiles("payfast", "png"),
	Peach: logoFiles("peach", "png"),
	Paystack: logoFiles("paystack", "png"),
	"Bob Pay": logoFiles("bob-pay", "png"),
	Stitch: logoFiles("stitch", "png"),
}

// Gateways with per-account settings are named "<Provider>-<account>", e.g. "Stripe-Main".
export const paymentGatewayLogo = (gateway: string): PaymentGatewayLogoFiles | undefined =>
	LOGOS[gateway.split("-")[0]]
