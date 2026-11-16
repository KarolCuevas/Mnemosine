import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import AccesoView from '../views/AccesoView.vue'
import BibliotecaView from '../views/BibliotecaView.vue'

const routes = [
  { path: '/acceso', name: 'acceso', component: AccesoView },
  { path: '/biblioteca', name: 'biblioteca', component: BibliotecaView, meta: { requiresAuth: true } },
  { path: '/', redirect: '/biblioteca' },
  { path: '/:pathMatch(.*)*', redirect: '/biblioteca' }
]

export const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.initialized) {
    await auth.fetchMe()
  }
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'acceso', query: { redirect: to.fullPath } }
  }
  if (to.name === 'acceso' && auth.isAuthenticated) {
    return { name: 'biblioteca' }
  }
  return true
})
