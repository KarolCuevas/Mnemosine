<template>
  <section class="player-bar" aria-label="Reproductor de música">
    <div class="player-track">
      <TrackArtwork :src="player.current?.cover_url" :seed="player.current?.album || player.current?.title || 'mnemosine'" />
      <div class="player-track-text">
        <template v-if="player.current">
          <RouterLink :to="{ name: 'detalle', params: { id: player.current.track_id } }" class="player-title">{{ player.current.title }}</RouterLink>
          <p>{{ player.current.artists || 'Artista desconocido' }}</p>
        </template>
        <template v-else><strong>Tu próxima canción te espera</strong><p>Elige algo de tu biblioteca</p></template>
        <p v-if="player.error" role="alert" class="player-error">{{ player.error }}</p>
      </div>
    </div>
    <div class="player-center">
      <div class="player-controls">
        <button type="button" class="icon-button" :disabled="!player.current" aria-label="Anterior" @click="player.previous()"><AppIcon name="previous" /></button>
        <button type="button" class="player-toggle" :disabled="!player.current" :aria-label="player.playing ? 'Pausar' : 'Reproducir'" :aria-pressed="player.playing" @click="player.toggle()"><AppIcon :name="player.playing ? 'pause' : 'play'" /></button>
        <button type="button" class="icon-button" :disabled="!player.current" aria-label="Siguiente" @click="player.next()"><AppIcon name="next" /></button>
      </div>
      <div class="player-progress">
        <span>{{ formatDuration(player.currentTime) }}</span>
        <input type="range" min="0" :max="Math.max(seekMax, 1)" step="0.1" :value="player.currentTime" :disabled="!player.current" aria-label="Posición de reproducción" :aria-valuetext="formatDuration(player.currentTime)" @input="player.seek(Number($event.target.value))" />
        <span>{{ formatDuration(seekMax) }}</span>
      </div>
    </div>
    <div class="player-volume"><AppIcon name="volume" /><label class="sr-only" for="volume">Volumen</label><input id="volume" type="range" min="0" max="1" step="0.01" :value="player.volume" @input="player.setVolume(Number($event.target.value))" /></div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { usePlayerStore } from '../stores/player'
import { formatDuration } from '../services/format'
import AppIcon from './AppIcon.vue'
import TrackArtwork from './TrackArtwork.vue'
const player = usePlayerStore()
const seekMax = computed(() => player.current ? player.duration || player.current.duration_seconds || 0 : 0)
</script>
