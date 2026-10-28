import assert from "node:assert/strict"
import { test } from "node:test"

import { SOUTH_AFRICAN_PROVINCES, stateChoice } from "./billingStates.ts"
import { INDIAN_STATES } from "./indianStates.ts"

test("rand orders offer the nine provinces", () => {
	const choice = stateChoice("VAT", "ZAR")
	assert.deepEqual(choice.options, SOUTH_AFRICAN_PROVINCES)
	assert.equal(choice.options?.length, 9)
	assert.equal(choice.kind, "province")
})

test("the currency wins over a GST label", () => {
	assert.deepEqual(stateChoice("GST", "ZAR").options, SOUTH_AFRICAN_PROVINCES)
})

test("rupee orders and GST offer the Indian states", () => {
	assert.deepEqual(stateChoice("Tax", "INR").options, INDIAN_STATES)
	assert.deepEqual(stateChoice(" gst ", "USD").options, INDIAN_STATES)
})

test("anywhere else the buyer types the region", () => {
	const choice = stateChoice("VAT", "EUR")
	assert.equal(choice.options, null)
	assert.equal(choice.kind, "region")
})
