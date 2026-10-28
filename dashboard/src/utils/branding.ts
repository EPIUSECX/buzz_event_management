import type { BrandingSettings } from "@/types"

export type BrandingDraft = Omit<BrandingSettings, "default_name">

const FIELDS = ["brand_name", "app_logo", "app_logo_dark", "app_icon", "favicon"] as const

export function draftOf(settings: BrandingSettings | null | undefined): BrandingDraft {
	return Object.fromEntries(
		FIELDS.map((field) => [field, settings?.[field] ?? null]),
	) as BrandingDraft
}

// Empty and missing are the same setting.
const normalised = (value: string | null) => (value ?? "").trim()

export function isBrandingDirty(draft: BrandingDraft, saved: BrandingDraft): boolean {
	return FIELDS.some((field) => normalised(draft[field]) !== normalised(saved[field]))
}

// The server refuses a light logo without a dark one and the other way round.
export function hasBrokenLogoPair(draft: BrandingDraft): boolean {
	return Boolean(draft.app_logo) !== Boolean(draft.app_logo_dark)
}
