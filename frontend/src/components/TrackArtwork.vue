<template>
  <span class="track-artwork" :data-tone="tone" aria-hidden="true">
    <img v-if="src && !imageFailed" :src="src" alt="" width="800" height="800" loading="lazy" decoding="async" @error="imageFailed = true" />
    <template v-else><span class="artwork-orbit"></span><AppIcon :name="icon" /></template>
  </span>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import AppIcon from './AppIcon.vue'
const props = defineProps({ seed: { type: [String, Number], default: '' }, icon: { type: String, default: 'music' }, src: { type: String, default: null } })
const imageFailed = ref(false)
watch(() => props.src, () => { imageFailed.value = false })
const tone = computed(() => [...String(props.seed)].reduce((sum, char) => sum + char.charCodeAt(0), 0) % 5)
</script>
