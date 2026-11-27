<template>
  <div class="app-shell">
    <a class="skip-link" href="#page-content">Saltar al contenido</a>
    <aside class="sidebar">
      <div class="brand-row">
        <RouterLink :to="{ name: 'biblioteca' }" class="brand" aria-label="Mnemosine, inicio">
          <span class="brand-mark"><AppIcon name="music" /></span>
          <span>mnemosine<span class="brand-dot">.</span></span>
        </RouterLink>
        <button class="icon-button mobile-menu" type="button" :aria-expanded="menuOpen" aria-controls="app-navigation" :aria-label="menuOpen ? 'Cerrar navegación' : 'Abrir navegación'" @click="menuOpen = !menuOpen">
          <AppIcon :name="menuOpen ? 'close' : 'menu'" />
        </button>
      </div>
      <div id="app-navigation" class="navigation-content" :class="{ 'is-open': menuOpen }">
        <nav aria-label="Principal" class="main-navigation">
          <p class="nav-caption">TU ESPACIO</p>
          <RouterLink v-for="item in navigation" :key="item.name" :to="{ name: item.name }" class="nav-link" :class="{ 'is-active': item.routes.includes(route.name) }">
            <AppIcon :name="item.icon" /><span>{{ item.label }}</span>
            <span v-if="item.routes.includes(route.name)" class="nav-indicator" aria-hidden="true"></span>
          </RouterLink>
          <p class="nav-caption nav-caption-secondary">TU MÚSICA</p>
          <RouterLink :to="{ name: 'cargar' }" class="nav-link" :class="{ 'is-active': route.name === 'cargar' }"><AppIcon name="upload" /><span>Subir música</span></RouterLink>
          <RouterLink v-if="auth.user?.role === 'ADMIN'" :to="{ name: 'admin' }" class="nav-link" :class="{ 'is-active': route.name === 'admin' }"><AppIcon name="shield" /><span>Administración</span></RouterLink>
        </nav>
        <div class="sidebar-bottom">
          <div class="sidebar-note"><AppIcon name="headphones" /><p>Una colección.<br /><strong>Infinitas formas de sentir.</strong></p></div>
          <div class="account-row">
            <span class="avatar">{{ initial }}</span>
            <div class="account-name"><strong>{{ displayName }}</strong><span>{{ auth.user?.role === 'ADMIN' ? 'Administrador' : 'Tu cuenta personal' }}</span></div>
            <button class="icon-button" type="button" aria-label="Cerrar sesión" title="Cerrar sesión" @click="logout"><AppIcon name="logout" /></button>
          </div>
        </div>
      </div>
    </aside>
    <div class="workspace">
      <header class="workspace-header">
        <div class="breadcrumb"><span>Tu espacio</span><AppIcon name="chevron" /><span>{{ route.meta.title }}</span></div>
        <span class="privacy-note"><AppIcon name="lock" /> Tu colección, a tu manera</span>
      </header>
      <main id="page-content" ref="content" class="page-content" tabindex="-1"><slot /></main>
    </div>
    <PlayerBar v-if="!['referencias', 'conexiones'].includes(route.name) || player.current" />
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { usePlayerStore } from '../stores/player'
import AppIcon from './AppIcon.vue'
import PlayerBar from './PlayerBar.vue'
const route = useRoute(), router = useRouter(), auth = useAuthStore(), player = usePlayerStore()
const menuOpen = ref(false), content = ref(null)
const displayName = computed(() => auth.user?.display_name || auth.user?.username || 'Mi cuenta')
const initial = computed(() => displayName.value.slice(0, 1).toLocaleUpperCase('es'))
const navigation = [
  { name: 'biblioteca', label: 'Mi biblioteca', icon: 'library', routes: ['biblioteca', 'detalle'] },
  { name: 'descubrir', label: 'Descubrir', icon: 'compass', routes: ['descubrir', 'coleccion'] },
  { name: 'referencias', label: 'Referencias musicales', icon: 'search', routes: ['referencias'] },
  { name: 'conexiones', label: 'Mi Google Drive', icon: 'lock', routes: ['conexiones'] },
  { name: 'listas', label: 'Mis listas', icon: 'list', routes: ['listas', 'lista'] },
]
watch(() => route.path, async () => {
  menuOpen.value = false
  await nextTick()
  content.value?.scrollTo({ top: 0 })
  content.value?.focus({ preventScroll: true })
})
async function logout() {
  player.reset()
  await auth.logout()
  router.push({ name: 'acceso' })
}
</script>
