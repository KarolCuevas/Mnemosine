import { defineStore } from 'pinia'
import { api } from '../services/api'

export const usePlayerStore = defineStore('player', {
  state: () => ({
    queue: [], // items: { track_id, title, artists, album, duration_seconds }
    index: -1,
    current: null,
    playing: false,
    currentTime: 0,
    duration: 0,
    volume: 0.8,
    audio: null
  }),
  actions: {
    ensureAudio() {
      if (this.audio) return this.audio
      const audio = new Audio()
      audio.preload = 'metadata'
      audio.volume = this.volume
      audio.addEventListener('play', () => { this.playing = true })
      audio.addEventListener('pause', () => { this.playing = false })
      audio.addEventListener('ended', () => { this.next() })
      audio.addEventListener('timeupdate', () => { this.currentTime = audio.currentTime })
      audio.addEventListener('loadedmetadata', () => { this.duration = audio.duration || 0 })
      audio.addEventListener('error', () => { this.playing = false })
      this.audio = audio
      return audio
    },
    playAt(position) {
      const item = this.queue[position]
      if (!item) return
      const audio = this.ensureAudio()
      this.index = position
      this.current = item
      this.currentTime = 0
      this.duration = item.duration_seconds || 0
      audio.src = api.audioUrl(item.track_id)
      audio.currentTime = 0
      audio.play().catch(() => { this.playing = false })
    },
    setQueue(items, startIndex = 0) {
      this.queue = items.filter((item) => item.available !== false)
      if (this.queue.length === 0) return
      this.playAt(Math.min(startIndex, this.queue.length - 1))
    },
    playSingle(item) {
      this.setQueue([item], 0)
    },
    toggle() {
      const audio = this.ensureAudio()
      if (!this.current) return
      if (this.playing) {
        audio.pause()
      } else {
        audio.play().catch(() => { this.playing = false })
      }
    },
    next() {
      if (this.index + 1 < this.queue.length) {
        this.playAt(this.index + 1)
      } else {
        const audio = this.ensureAudio()
        audio.pause()
        audio.currentTime = 0
        this.currentTime = 0
        this.playing = false
      }
    },
    previous() {
      const audio = this.ensureAudio()
      if (this.currentTime > 3 || this.index <= 0) {
        audio.currentTime = 0
        this.currentTime = 0
        return
      }
      this.playAt(this.index - 1)
    },
    seek(seconds) {
      const audio = this.ensureAudio()
      audio.currentTime = seconds
      this.currentTime = seconds
    },
    setVolume(value) {
      this.volume = value
      const audio = this.ensureAudio()
      audio.volume = value
    }
  }
})
