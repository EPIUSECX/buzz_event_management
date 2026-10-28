import assert from "node:assert/strict"
import { test } from "node:test"

import type { BrandingSettings } from "@/types"

import { draftOf, hasBrokenLogoPair, isBrandingDirty } from "./branding.ts"

const settings: BrandingSettings = {
	brand_name: "Acme Events",
	app_logo: "/files/light.png",
	app_logo_dark: "/files/dark.png",
	app_icon: null,
	favicon: null,
	default_name: "Buzz",
}

test("the draft keeps the five settings and drops the fallback name", () => {
	assert.deepEqual(draftOf(settings), {
		brand_name: "Acme Events",
		app_logo: "/files/light.png",
		app_logo_dark: "/files/dark.png",
		app_icon: null,
		favicon: null,
	})
})

test("a draft of nothing is empty", () => {
	assert.deepEqual(draftOf(undefined), {
		brand_name: null,
		app_logo: null,
		app_logo_dark: null,
		app_icon: null,
		favicon: null,
	})
})

test("an untouched draft is not dirty", () => {
	assert.equal(isBrandingDirty(draftOf(settings), draftOf(settings)), false)
})

test("empty text and no value are the same setting", () => {
	const saved = draftOf(settings)
	assert.equal(isBrandingDirty({ ...saved, favicon: "" }, saved), false)
	assert.equal(isBrandingDirty({ ...saved, brand_name: "Acme Events  " }, saved), false)
})

test("changing any setting makes the draft dirty", () => {
	const saved = draftOf(settings)
	assert.equal(isBrandingDirty({ ...saved, brand_name: "Other" }, saved), true)
	assert.equal(isBrandingDirty({ ...saved, favicon: "/files/fav.png" }, saved), true)
	assert.equal(isBrandingDirty({ ...saved, app_logo: null, app_logo_dark: null }, saved), true)
})

test("one logo without the other is a broken pair", () => {
	const saved = draftOf(settings)
	assert.equal(hasBrokenLogoPair(saved), false)
	assert.equal(hasBrokenLogoPair({ ...saved, app_logo_dark: null }), true)
	assert.equal(hasBrokenLogoPair({ ...saved, app_logo: null }), true)
	assert.equal(hasBrokenLogoPair({ ...saved, app_logo: null, app_logo_dark: null }), false)
})
