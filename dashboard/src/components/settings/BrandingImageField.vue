<script setup lang="ts">
import { Button, ErrorMessage, FileUploader, Spinner } from "frappe-ui"

import { validateIsImageFile } from "@/utils"

// The tile shows the image on the surface it will sit on, which is why it ignores the theme.
withDefaults(
	defineProps<{
		label: string
		description?: string
		surface?: "light" | "dark" | "neutral"
		square?: boolean
		// What shows when nothing is set, from the app that supplies the default brand.
		fallback?: string | null
	}>(),
	{ description: "", surface: "neutral", square: false, fallback: null },
)

const image = defineModel<string | null>({ required: true })

const SURFACES = {
	light: "bg-white",
	dark: "bg-[#171717]",
	neutral: "bg-surface-gray-2",
}
</script>

<template>
	<!-- Public: a guest sees these on the event pages, so a private upload would not load. -->
	<FileUploader
		:private="false"
		folder="Home/Attachments"
		file-types="image/*"
		:validate-file="validateIsImageFile"
		@success="(file: { file_url: string }) => (image = file.file_url)"
	>
		<template #default="{ openFileSelector, error: uploadError, uploading }">
			<div class="flex flex-col gap-2">
				<div>
					<p class="text-sm-medium text-ink-gray-8">{{ label }}</p>
					<p v-if="description" class="text-p-sm text-ink-gray-6">{{ description }}</p>
				</div>

				<div
					class="relative flex h-24 items-center justify-center overflow-hidden rounded-6 border border-outline-gray-2 p-3"
					:class="[SURFACES[surface], square ? 'w-24' : 'w-full']"
				>
					<Spinner v-if="uploading" class="size-5 text-ink-gray-5" />
					<img
						v-else-if="image"
						:src="image"
						:alt="label"
						class="max-h-full max-w-full object-contain"
					/>
					<template v-else-if="fallback">
						<img
							:src="fallback"
							:alt="label"
							class="max-h-full max-w-full object-contain opacity-80"
						/>
						<span
							class="absolute right-1.5 top-1.5 rounded-3 bg-surface-gray-3 px-1.5 text-xs text-ink-gray-6"
						>
							{{ __("Default") }}
						</span>
					</template>
					<span
						v-else
						class="text-p-sm"
						:class="surface === 'dark' ? 'text-white/60' : 'text-ink-gray-5'"
					>
						{{ __("Not set") }}
					</span>
				</div>

				<div class="flex gap-2">
					<Button size="sm" variant="outline" :disabled="uploading" @click="openFileSelector">
						{{ image ? __("Replace") : __("Upload") }}
					</Button>
					<Button
						v-if="image"
						size="sm"
						variant="ghost"
						:disabled="uploading"
						@click="image = null"
					>
						{{ __("Remove") }}
					</Button>
				</div>

				<ErrorMessage :message="uploadError ?? ''" />
			</div>
		</template>
	</FileUploader>
</template>
