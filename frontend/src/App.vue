<template>
  <AppShell v-if="auth.isAuthenticated && route.meta.requiresAuth"><RouterView :key="route.path" /></AppShell>
  <RouterView v-else />
</template>

<script setup>
import AppShell from './components/AppShell.vue'
import { useAuthStore } from './stores/auth'
import { useRoute } from 'vue-router'

const auth = useAuthStore()
const route = useRoute()
</script>
