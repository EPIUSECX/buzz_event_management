import assert from "node:assert/strict"
import { test } from "node:test"

import { paymentGatewayLogo } from "./paymentGateways.ts"

test("matches a gateway by its exact name", () => {
	assert.equal(
		paymentGatewayLogo("Razorpay")?.light,
		"/assets/buzz/images/payment_gateways/razorpay.svg",
	)
})

test("matches an account-suffixed gateway by its provider", () => {
	assert.equal(
		paymentGatewayLogo("Razorpay-Main")?.dark,
		"/assets/buzz/images/payment_gateways/razorpay-dark.svg",
	)
})

test("matches each South African gateway by the provider bma_integrations names it after", () => {
	const expected = {
		"Payfast-Main": "payfast",
		"Peach-Main": "peach",
		"Paystack-Main": "paystack",
		"Bob Pay-Main": "bob-pay",
		"Stitch-Main": "stitch",
	}
	for (const [gateway, file] of Object.entries(expected)) {
		assert.deepEqual(paymentGatewayLogo(gateway), {
			light: `/assets/buzz/images/payment_gateways/${file}.svg`,
			dark: `/assets/buzz/images/payment_gateways/${file}-dark.svg`,
		})
	}
})

test("returns nothing for an unknown gateway or offline method", () => {
	assert.equal(paymentGatewayLogo("Bank Transfer"), undefined)
})
