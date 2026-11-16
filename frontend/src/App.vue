<template>
  <router-view />
  <PlayerBar v-if="auth.isAuthenticated" />
</template>

<script setup>
import PlayerBar from './components/PlayerBar.vue'
import { useAuthStore } from './stores/auth'

const auth = useAuthStore()
</script>
