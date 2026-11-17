<template>
  <main class="min-h-screen bg-slate-950 pb-24 text-slate-100">
    <header class="border-b border-slate-800">
      <div class="mx-auto flex max-w-5xl items-center justify-between gap-4 px-6 py-4">
        <span class="text-lg font-semibold tracking-wide text-teal-300">Mnemosine</span>
        <nav aria-label="Principal" class="flex items-center gap-3 text-sm">
          <RouterLink :to="{ name: 'biblioteca' }" class="rounded-lg px-3 py-1.5 text-slate-300 transition hover:text-teal-300">Mi biblioteca</RouterLink>
          <span class="rounded-lg border border-teal-900 px-3 py-1.5 text-teal-300">Administración</span>
        </nav>
      </div>
    </header>

    <section class="mx-auto max-w-5xl px-6 py-6">
      <p class="text-xs font-medium uppercase tracking-[0.3em] text-teal-300">Administración</p>
      <h1 class="mt-1 text-3xl font-semibold">Plataforma</h1>

      <div role="tablist" aria-label="Secciones de administración" class="mt-5 flex flex-wrap gap-2 border-b border-slate-800 pb-3">
        <button v-for="tab in tabs" :key="tab.id" type="button" role="tab"
          class="rounded-lg px-3 py-1.5 text-sm transition"
          :class="activeTab === tab.id ? 'bg-teal-500 text-slate-950 font-medium' : 'text-slate-300 hover:text-teal-300'"
          :aria-selected="activeTab === tab.id"
          @click="activeTab = tab.id">
          {{ tab.label }}
        </button>
      </div>

      <!-- Cuentas -->
      <div v-if="activeTab === 'cuentas'" class="mt-4">
        <p v-if="error" role="alert" class="mb-3 rounded-lg border border-red-900 bg-red-950/60 px-3 py-2 text-sm text-red-300">{{ error }}</p>
        <p v-if="loading" class="text-slate-400">Cargando cuentas…</p>
        <table v-else class="w-full divide-y divide-slate-800 rounded-xl border border-slate-800 text-sm">
          <thead class="text-left text-xs uppercase text-slate-500">
            <tr><th class="px-3 py-2">Usuario</th><th class="px-3 py-2">Correo</th><th class="px-3 py-2">Rol</th><th class="px-3 py-2">Estado</th><th class="px-3 py-2">Acciones</th></tr>
          </thead>
          <tbody class="divide-y divide-slate-800">
            <tr v-for="user in users" :key="user.id">
              <td class="px-3 py-2 font-medium text-slate-100">{{ user.username }}</td>
              <td class="px-3 py-2 text-slate-400">{{ user.email }}</td>
              <td class="px-3 py-2">{{ user.role }}</td>
              <td class="px-3 py-2" :class="user.is_active ? 'text-teal-400' : 'text-amber-400'">{{ user.is_active ? 'Activa' : 'Desactivada' }}</td>
              <td class="px-3 py-2">
                <div class="flex flex-wrap gap-2">
                  <button type="button" class="rounded border border-slate-700 px-2 py-1 text-xs text-slate-300 hover:border-teal-400 hover:text-teal-300" @click="toggleRole(user)">{{ user.role === 'ADMIN' ? 'Hacer USER' : 'Hacer ADMIN' }}</button>
                  <button type="button" class="rounded border border-slate-700 px-2 py-1 text-xs text-slate-300 hover:border-teal-400 hover:text-teal-300" @click="toggleActive(user)">{{ user.is_active ? 'Desactivar' : 'Activar' }}</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Fuentes y escaneos -->
      <div v-else-if="activeTab === 'fuentes'" class="mt-4 space-y-4">
        <form class="flex flex-wrap items-end gap-2 rounded-xl border border-slate-800 p-4" @submit.prevent="createSource">
          <div>
            <label class="mb-1 block text-xs text-slate-400" for="src-name">Nombre</label>
            <input id="src-name" v-model="sourceForm.name" required maxlength="255" placeholder="Biblioteca" class="w-48 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm outline-none focus:border-teal-400" />
          </div>
          <div>
            <label class="mb-1 block text-xs text-slate-400" for="src-path">Carpeta (relativa a SCAN_ROOT)</label>
            <input id="src-path" v-model="sourceForm.base_relative_path" required maxlength="512" placeholder="biblioteca" class="w-64 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm outline-none focus:border-teal-400" />
          </div>
          <button type="submit" class="rounded-lg bg-teal-500 px-4 py-2 text-sm font-medium text-slate-950 hover:bg-teal-400 disabled:opacity-60" :disabled="sourceCreating">Registrar fuente</button>
        </form>

        <p v-if="scanStatusMessage" role="status" class="rounded-lg border border-teal-900 bg-teal-950/40 px-3 py-2 text-sm text-teal-300">{{ scanStatusMessage }}</p>

        <p v-if="loading" class="text-slate-400">Cargando fuentes…</p>
        <ul v-else class="divide-y divide-slate-800 rounded-xl border border-slate-800">
          <li v-for="source in sources" :key="source.source_id" class="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
            <div class="min-w-0">
              <span class="font-medium text-slate-100">{{ source.name }}</span>
              <span class="ml-2 text-xs text-slate-500">{{ source.base_relative_path }}</span>
              <span class="ml-2 rounded-full border px-2 py-0.5 text-[10px] uppercase" :class="source.status === 'ACTIVE' ? 'border-teal-800 text-teal-400' : 'border-amber-800 text-amber-400'">{{ source.status }}</span>
              <span class="block text-xs text-slate-500">{{ source.copies }} copias · último escaneo: {{ source.last_scanned_at ? formatDate(source.last_scanned_at) : 'nunca' }}</span>
            </div>
            <div class="flex flex-wrap items-center gap-2">
              <label class="sr-only" :for="'scan-owner-' + source.source_id">Propietario de la importación</label>
              <select :id="'scan-owner-' + source.source_id" v-model.number="scanOwners[source.source_id]" class="max-w-40 rounded-lg border border-slate-700 bg-slate-800 px-2 py-2 text-xs">
                <option v-for="user in users" :key="user.id" :value="user.id">{{ user.username }}</option>
              </select>
              <button type="button" class="rounded-lg bg-teal-500 px-3 py-2 text-xs font-medium text-slate-950 hover:bg-teal-400 disabled:opacity-50" :disabled="source.status !== 'ACTIVE' || scanning" @click="scan(source.source_id)">Escanear</button>
              <button type="button" class="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:border-teal-400 hover:text-teal-300" :disabled="!source.last_scan_job_id" @click="toggleDetails(source)">{{ details[source.source_id]?.open ? 'Ocultar detalle' : 'Ver detalle' }}</button>
              <button type="button" class="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:border-teal-400 hover:text-teal-300" @click="toggleSource(source)">{{ source.status === 'ACTIVE' ? 'Desconectar' : 'Conectar' }}</button>
            </div>
            <div v-if="details[source.source_id]?.open" class="mt-3 w-full border-t border-slate-800 pt-3">
              <p v-if="details[source.source_id].loading" class="text-xs text-slate-500">Cargando informe…</p>
              <p v-else-if="details[source.source_id].error" role="alert" class="text-xs text-red-300">{{ details[source.source_id].error }}</p>
              <div v-else>
                <p class="text-xs font-medium text-slate-400">Último escaneo (trabajo #{{ source.last_scan_job_id }}) — {{ details[source.source_id].files.length }} archivos</p>
                <ul class="mt-2 divide-y divide-slate-800 rounded-lg border border-slate-800 text-xs">
                  <li v-for="file in details[source.source_id].files" :key="file.scan_job_file_id" class="flex flex-wrap items-center gap-3 px-3 py-1.5">
                    <span class="rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase" :class="file.outcome === 'ADDED' ? 'border-teal-800 text-teal-400' : file.outcome === 'SKIPPED' ? 'border-slate-700 text-slate-400' : file.outcome === 'MISSING' ? 'border-amber-800 text-amber-400' : 'border-red-800 text-red-400'">{{ file.outcome }}</span>
                    <span class="min-w-0 flex-1 truncate text-slate-300">{{ file.relative_path }}</span>
                    <span class="hidden text-slate-500 md:inline">{{ file.artist || '' }}<span v-if="file.album"> · {{ file.album }}</span></span>
                    <span class="tabular-nums text-slate-500">{{ file.duration_seconds ? formatDuration(file.duration_seconds) : '' }}</span>
                    <span v-if="file.detail" class="w-full pl-2 text-[10px] text-slate-600">{{ file.detail }}</span>
                  </li>
                </ul>
              </div>
            </div>
          </li>
        </ul>
        <p v-if="!loading && sources.length === 0" class="text-center text-slate-500">Aún no hay fuentes registradas.</p>
      </div>

      <!-- Operaciones -->
      <div v-else-if="activeTab === 'operaciones'" class="mt-4">
        <div class="flex items-center gap-3">
          <label class="text-xs text-slate-400" for="op-filter">Tipo</label>
          <select id="op-filter" v-model="operationFilter" class="rounded-lg border border-slate-700 bg-slate-800 px-2 py-2 text-xs" @change="loadOperations(1)">
            <option value="">Todas</option><option value="UPLOAD">UPLOAD</option><option value="DOWNLOAD">DOWNLOAD</option><option value="SCAN">SCAN</option>
          </select>
          <span class="text-xs text-slate-500">{{ operations.total }} total</span>
        </div>
        <table class="mt-3 w-full divide-y divide-slate-800 rounded-xl border border-slate-800 text-xs">
          <thead class="text-left uppercase text-slate-500"><tr><th class="px-3 py-2">#</th><th class="px-3 py-2">Tipo</th><th class="px-3 py-2">Actor</th><th class="px-3 py-2">Resultado</th><th class="px-3 py-2">Detalle</th><th class="px-3 py-2">Fecha</th></tr></thead>
          <tbody class="divide-y divide-slate-800">
            <tr v-for="op in operations.items" :key="op.operation_id">
              <td class="px-3 py-2">{{ op.operation_id }}</td>
              <td class="px-3 py-2">{{ op.type }}</td>
              <td class="px-3 py-2">{{ op.actor_user_id ?? '—' }}</td>
              <td class="px-3 py-2" :class="op.result === 'SUCCESS' ? 'text-teal-400' : 'text-red-400'">{{ op.result }}</td>
              <td class="px-3 py-2 text-slate-400">{{ op.detail }}</td>
              <td class="px-3 py-2 text-slate-500">{{ formatDate(op.created_at) }}</td>
            </tr>
          </tbody>
        </table>
        <div class="mt-3 flex items-center justify-between">
          <button type="button" class="rounded-lg border border-slate-700 px-3 py-1.5 text-xs disabled:opacity-40" :disabled="operations.page <= 1" @click="loadOperations(operations.page - 1)">Anterior</button>
          <span class="text-xs text-slate-500">Página {{ operations.page }}</span>
          <button type="button" class="rounded-lg border border-slate-700 px-3 py-1.5 text-xs disabled:opacity-40" :disabled="operations.page * operations.page_size >= operations.total" @click="loadOperations(operations.page + 1)">Siguiente</button>
        </div>
      </div>

      <!-- Auditoría -->
      <div v-else-if="activeTab === 'auditoria'" class="mt-4">
        <p class="text-xs text-slate-500">{{ audit.total }} eventos registrados</p>
        <table class="mt-2 w-full divide-y divide-slate-800 rounded-xl border border-slate-800 text-xs">
          <thead class="text-left uppercase text-slate-500"><tr><th class="px-3 py-2">#</th><th class="px-3 py-2">Acción</th><th class="px-3 py-2">Actor</th><th class="px-3 py-2">Destino</th><th class="px-3 py-2">Detalle</th><th class="px-3 py-2">Fecha</th></tr></thead>
          <tbody class="divide-y divide-slate-800">
            <tr v-for="entry in audit.items" :key="entry.audit_id">
              <td class="px-3 py-2">{{ entry.audit_id }}</td>
              <td class="px-3 py-2">{{ entry.action }}</td>
              <td class="px-3 py-2">{{ entry.actor_user_id ?? '—' }}</td>
              <td class="px-3 py-2">{{ entry.target_user_id ?? ('copia ' + (entry.location_id ?? '—')) }}</td>
              <td class="px-3 py-2 text-slate-400">{{ entry.details ?? entry.declaration ?? '' }}</td>
              <td class="px-3 py-2 text-slate-500">{{ formatDate(entry.created_at) }}</td>
            </tr>
          </tbody>
        </table>
        <div class="mt-3 flex items-center justify-between">
          <button type="button" class="rounded-lg border border-slate-700 px-3 py-1.5 text-xs disabled:opacity-40" :disabled="audit.page <= 1" @click="loadAudit(audit.page - 1)">Anterior</button>
          <span class="text-xs text-slate-500">Página {{ audit.page }}</span>
          <button type="button" class="rounded-lg border border-slate-700 px-3 py-1.5 text-xs disabled:opacity-40" :disabled="audit.page * audit.page_size >= audit.total" @click="loadAudit(audit.page + 1)">Siguiente</button>
        </div>
      </div>
    </section>
  </main>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import { api, ApiError } from '../services/api'
import { formatDuration } from '../services/format'

const auth = useAuthStore()
const tabs = [
  { id: 'cuentas', label: 'Cuentas' },
  { id: 'fuentes', label: 'Fuentes y escaneos' },
  { id: 'operaciones', label: 'Operaciones' },
  { id: 'auditoria', label: 'Auditoría' }
]
const activeTab = ref('cuentas')
const users = ref([])
const sources = ref([])
const operations = ref({ items: [], total: 0, page: 1, page_size: 25 })
const audit = ref({ items: [], total: 0, page: 1, page_size: 25 })
const operationFilter = ref('')
const loading = ref(false)
const error = ref('')
const scanStatusMessage = ref('')
const scanning = ref(false)
const sourceCreating = ref(false)
const sourceForm = reactive({ name: '', base_relative_path: '' })
const scanOwners = reactive({})
const details = reactive({})

async function toggleDetails(source) {
  const id = source.source_id
  const current = details[id]
  if (current?.open) {
    current.open = false
    return
  }
  details[id] = { open: true, loading: true, error: '', files: [] }
  try {
    details[id].files = await api.scanJobFiles(source.last_scan_job_id)
  } catch {
    details[id].error = 'No se pudo cargar el informe del escaneo.'
  } finally {
    details[id].loading = false
  }
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString('es') : ''
}

async function loadUsers() {
  loading.value = true
  try {
    users.value = await api.adminUsers()
    for (const user of users.value) {
      if (!(user.id in scanOwners)) scanOwners[user.id] = user.id
    }
  } catch (err) {
    error.value = 'No se pudieron cargar las cuentas.'
  } finally {
    loading.value = false
  }
}

async function loadSources() {
  loading.value = true
  try {
    sources.value = await api.sources()
  } catch (err) {
    error.value = 'No se pudieron cargar las fuentes.'
  } finally {
    loading.value = false
  }
}

async function loadOperations(page = 1) {
  try {
    operations.value = await api.operations({ type: operationFilter.value, page, pageSize: 25 })
  } catch {
    error.value = 'No se pudieron cargar las operaciones.'
  }
}

async function loadAudit(page = 1) {
  try {
    audit.value = await api.permissionAudit({ page, pageSize: 25 })
  } catch {
    error.value = 'No se pudo cargar la auditoría.'
  }
}

async function toggleRole(user) {
  const next = user.role === 'ADMIN' ? 'USER' : 'ADMIN'
  try {
    await api.setUserRole(user.id, next)
    await loadUsers()
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : 'No se pudo cambiar el rol.'
  }
}

async function toggleActive(user) {
  try {
    if (user.is_active) await api.deactivateUser(user.id)
    else await api.activateUser(user.id)
    await loadUsers()
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : 'No se pudo cambiar el estado de la cuenta.'
  }
}

async function createSource() {
  sourceCreating.value = true
  error.value = ''
  try {
    await api.createSource({ name: sourceForm.name.trim(), base_relative_path: sourceForm.base_relative_path.trim() })
    sourceForm.name = ''
    sourceForm.base_relative_path = ''
    await loadSources()
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : 'No se pudo registrar la fuente.'
  } finally {
    sourceCreating.value = false
  }
}

async function scan(sourceId) {
  scanning.value = true
  scanStatusMessage.value = ''
  try {
    const job = await api.scanSource(sourceId, Number(scanOwners[sourceId]))
    scanStatusMessage.value = `Escaneo #${job.scan_job_id} en marcha…`
    const deadline = Date.now() + 120_000
    while (Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 1000))
      const current = await api.scanJob(job.scan_job_id)
      scanStatusMessage.value = `Escaneo #${job.scan_job_id}: ${current.status} · encontrados ${current.files_found} · añadidos ${current.files_added} · omitidos ${current.files_skipped}`
      if (['COMPLETED', 'FAILED', 'CANCELLED'].includes(current.status)) break
    }
    await loadSources()
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : 'No se pudo lanzar el escaneo.'
  } finally {
    scanning.value = false
  }
}

async function toggleSource(source) {
  const next = source.status === 'ACTIVE' ? 'DISCONNECTED' : 'ACTIVE'
  try {
    await api.setSourceStatus(source.source_id, next)
    await loadSources()
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : 'No se pudo cambiar el estado de la fuente.'
  }
}

onMounted(async () => {
  error.value = ''
  await loadUsers()
  await Promise.all([loadSources(), loadOperations(1), loadAudit(1)])
})
</script>
