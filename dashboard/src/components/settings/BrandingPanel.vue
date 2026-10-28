<script setup lang="ts">
import {
	Button,
	ErrorMessage,
	FormControl,
	SettingsBody,
	SettingsHeader,
	toast,
	useCall,
} from "frappe-ui"
import { computed, ref, watch } from "vue"

import BrandingImageField from "@/components/settings/BrandingImageField.vue"
import { userResource } from "@/data/user"
import type { BrandingSettings } from "@/types"
import { type BrandingDraft, draftOf, hasBrokenLogoPair, isBrandingDirty } from "@/utils/branding"
import { serverErrorMessage } from "@/utils/serverError"

// The dialog keeps its panels mounted, so opening it again is what reloads the settings
// and discards an abandoned edit.
const props = defineProps<{ open?: boolean }>()

const settings = ref<BrandingSettings | null>(null)
const draft = ref<BrandingDraft>(draftOf(null))
const saveError = ref("")

const isDirty = computed(() => isBrandingDirty(draft.value, draftOf(settings.value)))
const brokenPair = computed(() => hasBrokenLogoPair(draft.value))

function adopt(saved: BrandingSettings) {
	settings.value = saved
	draft.value = draftOf(saved)
}

const load = useCall<BrandingSettings>({
	url: "/api/v2/method/buzz.api.branding.get_branding",
	immediate: false,
	onSuccess: adopt,
	onError(error) {
		saveError.value = serverErrorMessage(error) || __("Could not load the branding")
	},
})

const save = useCall<BrandingSettings, BrandingDraft>({
	url: "/api/v2/method/buzz.api.branding.update_branding",
	method: "POST",
	immediate: false,
	async onSuccess(saved) {
		adopt(saved)
		saveError.value = ""
		// The sidebar, the theme preview and the tab icon all read the brand from here.
		await userResource.reload()
		showFavicon(userResource.data?.brand.favicon)
		toast.success(__("Branding updated"))
	},
	onError(error) {
		saveError.value = serverErrorMessage(error) || __("Could not update the branding")
	},
})

watch(
	() => props.open,
	(isOpen) => {
		if (!isOpen) return
		saveError.value = ""
		load.reload()
	},
	{ immediate: true },
)

function submit() {
	saveError.value = ""
	save.submit({ ...draft.value })
}

// The server writes the favicon into the page it serves; this carries a change to the open tab.
function showFavicon(url: string | undefined) {
	const link = document.querySelector<HTMLLinkElement>('link[rel~="icon"]')
	if (link && url) link.href = url
}
</script>

<template>
	<SettingsHeader
		:title="__('Branding')"
		:description="
			__('The name, logos and icons across the dashboard, public pages, emails and share images.')
		"
	>
		<template #actions>
			<Transition name="save">
				<Button
					v-if="isDirty || save.loading"
					variant="solid"
					:loading="save.loading"
					:disabled="brokenPair"
					@click="submit"
				>
					{{ __("Save") }}
				</Button>
			</Transition>
		</template>
	</SettingsHeader>

	<SettingsBody>
		<div class="flex flex-col gap-8 pt-6">
			<section class="flex flex-col gap-2">
				<FormControl
					type="text"
					:label="__('Brand name')"
					:placeholder="settings?.default_name"
					:model-value="draft.brand_name ?? ''"
					@update:model-value="(value: string) => (draft.brand_name = value)"
				/>
				<p class="text-p-sm text-ink-gray-6">
					{{ __("Names the site in tooltips. Empty uses the site's app name there.") }}
				</p>
				<FormControl
					type="checkbox"
					:label="__('Show the name beside the logo')"
					:disabled="!draft.brand_name?.trim()"
					:model-value="draft.show_brand_name"
					@update:model-value="(value: boolean) => (draft.show_brand_name = value)"
				/>
				<p class="text-p-sm text-ink-gray-6">
					{{ __("Leave this off when your logo already includes the name.") }}
				</p>
			</section>

			<section class="flex flex-col gap-3">
				<div>
					<h3 class="text-lg-semibold text-ink-gray-8">{{ __("Logo") }}</h3>
					<p class="text-p-sm text-ink-gray-6">
						{{
							__(
								"Replaces the Buzz logo on the dashboard, public pages, emails and event share images. Upload both, or neither.",
							)
						}}
					</p>
				</div>
				<div class="grid gap-4 sm:grid-cols-2">
					<BrandingImageField
						v-model="draft.app_logo"
						surface="light"
						:label="__('Light mode')"
						:description="__('Shown on light pages')"
					/>
					<BrandingImageField
						v-model="draft.app_logo_dark"
						surface="dark"
						:label="__('Dark mode')"
						:description="__('Shown on dark pages')"
					/>
				</div>
				<ErrorMessage
					v-if="brokenPair"
					:message="__('Upload both the light and dark logo, or neither.')"
				/>
			</section>

			<section class="flex flex-col gap-3">
				<h3 class="text-lg-semibold text-ink-gray-8">{{ __("Icons") }}</h3>
				<div class="grid gap-4 sm:grid-cols-2">
					<BrandingImageField
						v-model="draft.app_icon"
						square
						:label="__('App icon')"
						:description="__('A square mark for the collapsed sidebar and the Desk apps screen')"
					/>
					<BrandingImageField
						v-model="draft.favicon"
						square
						:label="__('Favicon')"
						:description="__('The browser tab icon')"
					/>
				</div>
			</section>

			<ErrorMessage :message="saveError" />
		</div>
	</SettingsBody>
</template>

<style scoped>
/* Matches the Profile panel's Save transition. */
.save-enter-active {
	transition:
		opacity 150ms cubic-bezier(0.23, 1, 0.32, 1),
		transform 150ms cubic-bezier(0.23, 1, 0.32, 1);
}

.save-leave-active {
	transition:
		opacity 100ms cubic-bezier(0.23, 1, 0.32, 1),
		transform 100ms cubic-bezier(0.23, 1, 0.32, 1);
}

.save-enter-from,
.save-leave-to {
	opacity: 0;
	transform: scale(0.95);
}

@media (prefers-reduced-motion: reduce) {
	.save-enter-from,
	.save-leave-to {
		transform: none;
	}
}
</style>
