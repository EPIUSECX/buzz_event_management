import { INDIAN_STATES } from "./indianStates.ts"

export const SOUTH_AFRICAN_PROVINCES = [
	"Eastern Cape",
	"Free State",
	"Gauteng",
	"KwaZulu-Natal",
	"Limpopo",
	"Mpumalanga",
	"North West",
	"Northern Cape",
	"Western Cape",
]

export interface StateChoice {
	// The list to pick from, or null where the buyer types it.
	options: string[] | null
	kind: "province" | "state" | "region"
}

/**
 * Which regions the billing address offers. India's GST needs the state for place of supply, and
 * South African orders are in rand. Anywhere else the buyer types it, since a list would be wrong.
 */
export function stateChoice(taxLabel: string, currency: string): StateChoice {
	if (currency === "ZAR") return { options: SOUTH_AFRICAN_PROVINCES, kind: "province" }
	if (currency === "INR" || isGst(taxLabel)) return { options: INDIAN_STATES, kind: "state" }
	return { options: null, kind: "region" }
}

const isGst = (taxLabel: string) => taxLabel.trim().toUpperCase() === "GST"
