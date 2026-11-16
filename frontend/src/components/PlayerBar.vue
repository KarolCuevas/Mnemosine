<template>
  <div class="fixed inset-x-0 bottom-0 z-20 border-t border-slate-800 bg-slate-900/95 backdrop-blur"
    style="padding-bottom: max(env(safe-area-inset-bottom), 0px)">
    <div class="mx-auto flex max-w-5xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2">
      <div class="min-w-0 flex-1 basis-48">
        <p v-if="player.current" class="truncate text-sm font-medium text-slate-100">{{ player.current.title }}</p>
        <p v-if="player.current" class="truncate text-xs text-slate-400">{{ player.current.artists }}</p>
        <p v-else class="text-xs text-slate-500">Nada en reproducción</p>
      </div>

      <div class="flex items-center gap-1">
        <button type="button" class="rounded-full p-2 text-slate-300 transition hover:bg-slate-800 hover:text-teal-300 disabled:opacity-40"
          :disabled="!player.current" aria-label="Anterior" @click="player.previous()">
          <svg viewBox="0 0 24 24" class="h-5 w-5" fill="currentColor" aria-hidden="true"><path d="M6 6h2v12H6zM18 6l-8.5 6L18 18z"/></svg>
        </button>
        <button type="button" class="rounded-full bg-teal-500 p-2 text-slate-950 transition hover:bg-teal-400 disabled:opacity-40"
          :disabled="!player.current" :aria-label="player.playing ? 'Pausar' : 'Reproducir'" :aria-pressed="player.playing" @click="player.toggle()">
          <svg v-if="!player.playing" viewBox="0 0 24 24" class="h-5 w-5" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>
          <svg v-else viewBox="0 0 24 24" class="h-5 w-5" fill="currentColor" aria-hidden="true"><path d="M7 5h4v14H7zM13 5h4v14h-4z"/></svg>
        </button>
        <button type="button" class="rounded-full p-2 text-slate-300 transition hover:bg-slate-800 hover:text-teal-300 disabled:opacity-40"
          :disabled="!player.current" aria-label="Siguiente" @click="player.next()">
          <svg viewBox="0 0 24 24" class="h-5 w-5" fill="currentColor" aria-hidden="true"><path d="M16 6h2v12h-2zM6 6l8.5 6L6 18z"/></svg>
        </button>
      </div>

      <div class="flex min-w-0 flex-[2] basis-64 items-center gap-2">
        <span class="text-xs tabular-nums text-slate-400">{{ formatDuration(player.currentTime) }}</span>
        <input type="range" class="seek h-2 w-full accent-teal-400" min="0" :max="Math.max(seekMax, 1)" step="0.1"
          :value="player.currentTime" :disabled="!player.current" aria-label="Posición de reproducción"
          @input="onSeek" />
        <span class="text-xs tabular-nums text-slate-400">{{ formatDuration(player.current ? (player.duration || player.current.duration_seconds) : 0) }}</span>
      </div>

      <div class="flex items-center gap-2">
        <label class="text-xs font-medium text-slate-400" for="volume">Volumen</label>
        <input id="volume" type="range" class="h-2 w-24 accent-teal-400" min="0" max="1" step="0.01"
          :value="player.volume" aria-label="Volumen" @input="onVolume" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { usePlayerStore } from '../stores/player'
import { formatDuration } from '../services/format'

const player = usePlayerStore()

const seekMax = computed(() => player.duration || player.current?.duration_seconds || 0)

function onSeek(event) {
  player.seek(Number(event.target.value))
}

function onVolume(event) {
  player.setVolume(Number(event.target.value))
}
</script>
