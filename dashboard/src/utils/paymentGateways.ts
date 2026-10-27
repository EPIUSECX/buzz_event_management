const LOGO_DIRECTORY = "/assets/buzz/images/payment_gateways"

// Brand marks are drawn for one background, so each gateway ships a version per theme.
interface PaymentGatewayLogoFiles {
	light: string
	dark: string
}

const logoFiles = (name: string): PaymentGatewayLogoFiles => ({
	light: `${LOGO_DIRECTORY}/${name}.svg`,
	dark: `${LOGO_DIRECTORY}/${name}-dark.svg`,
})

// Keyed by the provider part of the gateway's name. The South African gateways come from
// bma_integrations, which names them "Payfast-<account>", "Peach-<account>" and so on. Their
// files are typeset wordmarks for now: swap in each brand's official mark under the same name.
const LOGOS: Record<string, PaymentGatewayLogoFiles> = {
	Razorpay: logoFiles("razorpay"),
	Payfast: logoFiles("payfast"),
	Peach: logoFiles("peach"),
	Paystack: logoFiles("paystack"),
	"Bob Pay": logoFiles("bob-pay"),
	Stitch: logoFiles("stitch"),
}

// Gateways with per-account settings are named "<Provider>-<account>", e.g. "Stripe-Main".
export const paymentGatewayLogo = (gateway: string): PaymentGatewayLogoFiles | undefined =>
	LOGOS[gateway.split("-")[0]]
