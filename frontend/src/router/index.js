import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import AccesoView from '../views/AccesoView.vue'
import BibliotecaView from '../views/BibliotecaView.vue'
import CargarView from '../views/CargarView.vue'
import DetalleView from '../views/DetalleView.vue'
import DescubrirView from '../views/DescubrirView.vue'
import ColeccionView from '../views/ColeccionView.vue'
import ListasView from '../views/ListasView.vue'
import ListaDetalleView from '../views/ListaDetalleView.vue'
import AdminView from '../views/AdminView.vue'

const routes = [
  { path: '/acceso', name: 'acceso', component: AccesoView, meta: { title: 'Acceso' } },
  { path: '/biblioteca', name: 'biblioteca', component: BibliotecaView, meta: { requiresAuth: true, title: 'Mi biblioteca' } },
  { path: '/biblioteca/cargar', name: 'cargar', component: CargarView, meta: { requiresAuth: true, title: 'Cargar música' } },
  { path: '/cancion/:id(\\d+)', name: 'detalle', component: DetalleView, meta: { requiresAuth: true, title: 'Detalle' } },
  { path: '/descubrir', name: 'descubrir', component: DescubrirView, meta: { requiresAuth: true, title: 'Descubrir' } },
  { path: '/descubrir/:username', name: 'coleccion', component: ColeccionView, meta: { requiresAuth: true, title: 'Colección pública' } },
  { path: '/listas', name: 'listas', component: ListasView, meta: { requiresAuth: true, title: 'Mis listas' } },
  { path: '/listas/:id(\\d+)', name: 'lista', component: ListaDetalleView, meta: { requiresAuth: true, title: 'Lista' } },
  { path: '/admin', name: 'admin', component: AdminView, meta: { requiresAuth: true, requiresAdmin: true, title: 'Administración' } },
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
  if (to.meta.requiresAdmin && auth.user?.role !== 'ADMIN') {
    return { name: 'biblioteca' }
  }
  if (to.name === 'acceso' && auth.isAuthenticated) {
    return { name: 'biblioteca' }
  }
  return true
})

router.afterEach((to) => {
  const title = to.meta.title ?? 'Mnemosine'
  document.title = `${title} | Mnemosine`
})
