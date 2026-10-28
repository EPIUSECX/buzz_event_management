import type { BrandingSettings } from "@/types"

export type BrandingDraft = Omit<
	BrandingSettings,
	"default_name" | "default_logo" | "default_logo_dark" | "default_icon" | "default_favicon"
>

const TEXT_FIELDS = ["brand_name", "app_logo", "app_logo_dark", "app_icon", "favicon"] as const

export function draftOf(settings: BrandingSettings | null | undefined): BrandingDraft {
	return {
		...(Object.fromEntries(TEXT_FIELDS.map((field) => [field, settings?.[field] ?? null])) as Omit<
			BrandingDraft,
			"show_brand_name"
		>),
		show_brand_name: settings?.show_brand_name ?? false,
	}
}

// Empty and missing are the same setting.
const normalised = (value: string | null) => (value ?? "").trim()

export function isBrandingDirty(draft: BrandingDraft, saved: BrandingDraft): boolean {
	return (
		TEXT_FIELDS.some((field) => normalised(draft[field]) !== normalised(saved[field])) ||
		draft.show_brand_name !== saved.show_brand_name
	)
}

// The server refuses a light logo without a dark one and the other way round.
export function hasBrokenLogoPair(draft: BrandingDraft): boolean {
	return Boolean(draft.app_logo) !== Boolean(draft.app_logo_dark)
}
