import { defineStore } from 'pinia'
import { api, ApiError } from '../services/api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    initialized: false,
    loading: false
  }),
  getters: {
    isAuthenticated: (state) => state.user !== null
  },
  actions: {
    async fetchMe() {
      try {
        this.user = await api.me()
      } catch {
        this.user = null
      } finally {
        this.initialized = true
      }
    },
    async login(identity, password) {
      this.loading = true
      try {
        this.user = await api.login(identity, password)
      } finally {
        this.loading = false
      }
    },
    async register(payload) {
      this.loading = true
      try {
        this.user = await api.register(payload)
      } finally {
        this.loading = false
      }
    },
    async logout() {
      try {
        await api.logout()
      } catch {
        // la sesión del servidor puede haber caducado ya; limpiamos igualmente
      } finally {
        this.user = null
      }
    }
  }
})

export { ApiError }
