<template>
  <div class="page library-page">
    <section class="library-hero" aria-labelledby="library-title">
      <div class="hero-copy">
        <p class="eyebrow">TU ESPACIO SONORO</p>
        <h1 id="library-title">Tus canciones<span class="accent-dot">.</span></h1>
        <p>La música que te acompaña.<br />Un lugar para hacerla tuya.</p>
        <RouterLink :to="{ name: 'cargar' }" class="button button-dark"><AppIcon name="plus" /> Subir música</RouterLink>
      </div>
      <div class="hero-art" aria-hidden="true"><div class="record-sleeve"><span>M / 01</span><div class="sleeve-lines"></div><span>YOUR PERSONAL SOUNDTRACK</span></div><div class="vinyl"><div class="vinyl-label"><AppIcon name="music" /></div></div><span class="hero-art-caption">RECUERDOS EN REPRODUCCIÓN</span></div>
    </section>

    <div class="library-layout">
      <section aria-labelledby="collection-title" class="collection-section">
        <div class="section-heading">
          <div><p class="eyebrow">HECHA POR TI</p><h2 id="collection-title">Tu colección <span class="count-badge">{{ total }}</span></h2></div>
          <button v-if="items.some(item => item.available)" type="button" class="button button-quiet" @click="playFromList(0)"><AppIcon name="play" /> Reproducir selección</button>
        </div>
        <div class="library-toolbar">
          <form class="search-field" role="search" @submit.prevent="load">
            <AppIcon name="search" /><label for="buscar" class="sr-only">Buscar en tu biblioteca</label>
            <input id="buscar" v-model="query" type="search" placeholder="Buscar canción, artista o álbum" autocomplete="off" />
            <button v-if="query" class="icon-button" type="button" aria-label="Limpiar búsqueda" @click="query = ''"><AppIcon name="close" /></button>
          </form>
          <div class="view-switch" role="group" aria-label="Presentación de canciones">
            <button class="icon-button" :class="{ selected: view === 'list' }" type="button" aria-label="Vista de lista" :aria-pressed="view === 'list'" @click="view = 'list'"><AppIcon name="rows" /></button>
            <button class="icon-button" :class="{ selected: view === 'grid' }" type="button" aria-label="Vista de cuadrícula" :aria-pressed="view === 'grid'" @click="view = 'grid'"><AppIcon name="grid" /></button>
          </div>
        </div>
        <p class="sr-only" role="status">{{ loading ? 'Cargando canciones' : `${total} canciones encontradas` }}</p>
        <div v-if="loading" class="loading-state" aria-hidden="true"><span v-for="n in 5" :key="n" class="skeleton-row"></span></div>
        <div v-else-if="error" class="empty-state"><AppIcon name="library" /><p role="alert">{{ error }}</p><button class="button button-secondary" @click="load">Volver a intentar</button></div>
        <div v-else-if="items.length === 0" class="empty-state">
          <span class="empty-icon"><AppIcon :name="query ? 'search' : 'music'" /></span>
          <h3>{{ query ? 'No encontramos esa canción' : 'Tu colección empieza aquí' }}</h3>
          <p>{{ query ? 'Prueba con otro título, artista o álbum.' : 'Sube tu primera canción y dale vida a tu biblioteca.' }}</p>
          <button v-if="query" type="button" class="button button-secondary" @click="query = ''">Limpiar búsqueda</button>
          <RouterLink v-else :to="{ name: 'cargar' }" class="button button-primary"><AppIcon name="upload" /> Subir mi primera canción</RouterLink>
        </div>
        <template v-else>
          <div v-if="view === 'list'" class="track-list-heading" aria-hidden="true"><span>#</span><span>CANCIÓN</span><span>ÁLBUM</span><AppIcon name="clock" /></div>
          <ul class="track-collection" :class="view === 'grid' ? 'track-grid' : 'track-list'" aria-label="Canciones de tu biblioteca">
            <li v-for="(item, index) in items" :key="item.location_id" class="track-item" :class="{ 'is-playing': player.current?.location_id === item.location_id, unavailable: !item.available }">
              <span class="track-number" aria-hidden="true">{{ (page - 1) * pageSize + index + 1 }}</span>
              <div class="track-identity">
                <div class="track-cover"><TrackArtwork :src="item.cover_url" :seed="item.album || item.title" /><button type="button" class="cover-play" :disabled="!item.available" :aria-label="`Reproducir ${item.title}`" @click="playFromList(index)"><AppIcon name="play" /></button></div>
                <RouterLink :to="{ name: 'detalle', params: { id: item.track_id } }" class="track-description"><strong>{{ item.title }}</strong><span>{{ item.artists || 'Artista desconocido' }}</span></RouterLink>
              </div>
              <span class="track-album">{{ item.album || 'Sin álbum' }}</span>
              <span class="track-duration">{{ item.available ? formatDuration(item.duration_seconds) : 'No disponible' }}</span>
            </li>
          </ul>
          <nav v-if="totalPages > 1" aria-label="Páginas de la biblioteca" class="pagination"><button type="button" class="button button-secondary" :disabled="page === 1" @click="goToPage(page - 1)">Anterior</button><span>{{ page }} / {{ totalPages }}</span><button type="button" class="button button-secondary" :disabled="page >= totalPages" @click="goToPage(page + 1)">Siguiente</button></nav>
        </template>

        <section v-if="sharedItems.length || sharedError" class="shared-section" aria-labelledby="shared-title">
          <div class="section-heading"><h2 id="shared-title">Compartidas contigo</h2><span class="count-badge">{{ sharedItems.length }}</span></div>
          <p v-if="sharedError" class="muted" role="alert">{{ sharedError }} <button class="text-link" @click="loadShared">Reintentar</button></p>
          <ul v-else class="shared-list"><li v-for="(item, index) in sharedItems" :key="item.location_id"><TrackArtwork :src="item.cover_url" :seed="item.title" /><RouterLink :to="{ name: 'detalle', params: { id: item.track_id } }"><strong>{{ item.title }}</strong><span>{{ item.artists }} · de @{{ item.owner_username }}</span></RouterLink><button type="button" class="icon-button" :disabled="!item.can_stream" :aria-label="`Reproducir ${item.title}`" @click="playShared(index)"><AppIcon name="play" /></button></li></ul>
        </section>
      </section>

      <aside class="library-aside" aria-label="Explora tu espacio">
        <p class="eyebrow">SIGUE EXPLORANDO</p>
        <RouterLink :to="{ name: 'listas' }" class="explore-card"><span class="explore-icon"><AppIcon name="list" /></span><h3>Un momento.<br />Una lista.</h3><p>Agrupa tus canciones para cada ocasión.</p><span class="text-link">Crear mi selección <AppIcon name="arrow" /></span></RouterLink>
        <RouterLink :to="{ name: 'referencias' }" class="reference-shortcut"><AppIcon name="compass" /><div><h3>Encuentra esa canción</h3><p>Explora nombres y artistas con MusicBrainz.</p></div><AppIcon name="arrow" /></RouterLink>
        <div class="privacy-tip"><AppIcon name="lock" /><p>Lo que subes es privado.<br />Tú decides con quién compartirlo.</p></div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { usePlayerStore } from '../stores/player'
import { api } from '../services/api'
import { formatDuration } from '../services/format'
import AppIcon from '../components/AppIcon.vue'
import TrackArtwork from '../components/TrackArtwork.vue'
const player = usePlayerStore()
const query = ref(''), items = ref([]), total = ref(0), page = ref(1), pageSize = 24
const loading = ref(true), error = ref(''), sharedItems = ref([]), sharedError = ref(''), view = ref('list')
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
let searchTimer, requestId = 0
watch(query, () => {
  clearTimeout(searchTimer)
  requestId++
  page.value = 1
  searchTimer = setTimeout(load, 250)
})
async function load() {
  clearTimeout(searchTimer)
  const id = ++requestId
  loading.value = true
  error.value = ''
  try {
    const data = await api.library({ q: query.value.trim(), page: page.value, pageSize })
    if (id !== requestId) return
    items.value = data.items
    total.value = data.total
  } catch {
    if (id === requestId) error.value = 'No se pudo cargar la biblioteca. Revisa tu conexión e inténtalo de nuevo.'
  } finally {
    if (id === requestId) loading.value = false
  }
}
function playFromList(index) { player.setQueue(items.value, index) }
function playShared(index) {
  const playable = sharedItems.value.filter(item => item.can_stream)
  const selected = playable.indexOf(sharedItems.value[index])
  if (selected >= 0) player.setQueue(playable.map(item => ({ ...item, available: true })), selected)
}
function goToPage(target) { page.value = target; load() }
async function loadShared() {
  sharedError.value = ''
  try { sharedItems.value = (await api.sharedWithMe()).items }
  catch { sharedError.value = 'No se pudieron cargar las canciones compartidas.' }
}
onMounted(() => { load(); loadShared() })
onUnmounted(() => { clearTimeout(searchTimer); requestId++ })
</script>
