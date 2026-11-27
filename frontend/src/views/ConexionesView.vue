<template>
  <div class="page drive-page">
    <section class="page-section">
      <h1 class="text-3xl font-semibold">Mi Google Drive</h1>
      <p class="mt-3 max-w-2xl text-slate-300">Conecta tu cuenta y elige los audios que quieras usar en Mnemosine. Solo tendremos acceso a los archivos que elijas o que cree la aplicación.</p>
      <p role="status" class="mt-4 min-h-6 text-teal-200">{{ message }}</p>
      <p v-if="error" role="alert" class="mt-3 rounded-xl border border-red-800 bg-red-950 p-4 text-red-200">{{ error }}</p>
      <progress v-if="busy" aria-label="Procesando conexión con Drive" class="mt-3 w-full" />

      <section class="mt-5 rounded-xl border border-slate-700 bg-slate-900 p-5" aria-labelledby="drive-account-heading" :aria-busy="busy">
        <h2 id="drive-account-heading" class="text-xl font-semibold">Tu conexión</h2>
        <p class="mt-2 font-medium">{{ statusLabel }}</p>
        <p v-if="connection?.email" class="mt-1 break-all text-slate-300">{{ connection.email }}</p>
        <p v-if="!configured && !loading" class="mt-3 text-amber-200">{{ configMessage || 'Google Drive no está disponible en esta instalación.' }}</p>
        <p v-if="wrongOrigin" class="mt-3 text-amber-200">Para conectar Google, abre <a :href="origin + '/conexiones'" class="underline">Mnemosine en su dirección configurada</a>.</p>
        <p v-if="connection?.status === 'REAUTH_REQUIRED'" class="mt-3 text-amber-200">El permiso venció o fue retirado. Reconecta la misma cuenta para recuperar tu selección.</p>
        <p v-if="connection?.status === 'REVOCATION_PENDING'" class="mt-3 text-amber-200">Mnemosine ya bloqueó la conexión. Falta confirmar la revocación en Google; pulsa Terminar desconexión para reintentarlo.</p>
        <div class="mt-5 flex flex-wrap gap-3">
          <button v-if="connection?.status !== 'ACTIVE' && connection?.status !== 'REVOCATION_PENDING'" type="button" :disabled="busy || !configured || wrongOrigin" class="drive-primary" @click="connect">{{ connection?.status === 'REAUTH_REQUIRED' ? 'Reconectar Google Drive' : 'Conectar Google Drive' }}</button>
          <button v-if="connection?.status === 'ACTIVE'" ref="pickerButton" type="button" :disabled="busy || !configured || wrongOrigin" class="drive-primary" @click="pick">Elegir un audio de Drive</button>
          <button v-if="connection && connection.status !== 'DISCONNECTED'" type="button" :disabled="busy" class="drive-secondary" @click="confirmDisconnect = true">{{ connection.status === 'REVOCATION_PENDING' ? 'Terminar desconexión' : 'Desconectar Google Drive' }}</button>
          <button type="button" :disabled="busy" class="drive-secondary" @click="run(refresh)">Actualizar estado</button>
        </div>
        <div v-if="confirmDisconnect" class="mt-4 rounded-lg border border-amber-600 p-4" role="group" aria-labelledby="disconnect-question">
          <p id="disconnect-question">Se retirará el acceso de Mnemosine a tu Drive y se quitará esta selección. Los archivos originales permanecerán en Google Drive.</p>
          <div class="mt-3 flex flex-wrap gap-3">
            <button type="button" class="drive-secondary" :disabled="busy" @click="disconnect">Confirmar desconexión</button>
            <button type="button" class="drive-secondary" :disabled="busy" @click="confirmDisconnect = false">Cancelar</button>
          </div>
        </div>
        <p class="mt-4 text-sm text-slate-400">Durante las pruebas de Google, el permiso puede vencer a los siete días. Cada persona debe conectar su propia cuenta.</p>
      </section>

      <section v-if="connection?.status === 'ACTIVE'" class="mt-7" aria-labelledby="drive-files-heading">
        <h2 id="drive-files-heading" class="text-xl font-semibold">Tu selección privada</h2>
        <p class="mt-2 max-w-2xl text-slate-300">Estos archivos permanecen en Drive. La selección comprueba acceso y datos del archivo; todavía no valida el audio ni lo incorpora a la biblioteca.</p>
        <p v-if="!files.length && !busy" class="mt-5 text-slate-400">Aún no has elegido archivos. Seleccionar una carpeta no autoriza todos los archivos que contiene.</p>
        <ul class="mt-4 grid gap-3" role="list">
          <li v-for="file in files" :key="file.id" class="rounded-xl border border-slate-700 bg-slate-900 p-5">
            <h3 class="break-words font-semibold">{{ file.name }}</h3>
            <p class="mt-1 text-sm text-slate-400">{{ size(file.size_bytes) }} · Audio pendiente de validar</p>
            <div class="mt-3 flex flex-wrap gap-3">
              <button type="button" :disabled="busy" class="drive-secondary" :aria-label="'Comprobar acceso: ' + file.name" @click="verify(file)">Comprobar acceso</button>
              <button type="button" :disabled="busy" class="drive-secondary" :aria-label="'Quitar selección: ' + file.name" @click="remove(file)">Quitar selección</button>
            </div>
          </li>
        </ul>
        <nav v-if="total > 25" aria-label="Páginas de la selección" class="mt-4 flex flex-wrap items-center gap-3">
          <button type="button" class="drive-secondary" :disabled="busy || page === 1" @click="changePage(-1)">Anterior</button>
          <span>Página {{ page }}</span>
          <button type="button" class="drive-secondary" :disabled="busy || page * 25 >= total" @click="changePage(1)">Siguiente</button>
        </nav>
      </section>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../services/api'
import { chooseDriveFiles, loadPickerLibrary } from '../services/googlePicker'

const route = useRoute(), router = useRouter()
const connection = ref(null), configured = ref(false), configMessage = ref(''), origin = ref('')
const loading = ref(true), busy = ref(false), message = ref(''), error = ref('')
const files = ref([]), total = ref(0), page = ref(1), confirmDisconnect = ref(false), pickerButton = ref(null)
const controller = new AbortController()
const wrongOrigin = computed(() => origin.value && origin.value !== window.location.origin)
const statusLabel = computed(() => ({ ACTIVE: 'Conectada', REAUTH_REQUIRED: 'Necesita reconexión', REVOCATION_PENDING: 'Desconexión pendiente', DISCONNECTED: 'Sin conexión' }[connection.value?.status] || (loading.value ? 'Consultando…' : 'Sin conexión')))
const outcomes = {
  connected: 'Tu Google Drive quedó conectado.', cancelled: 'Cancelaste la autorización. Puedes volver a intentarlo.',
  invalid_state: 'La autorización venció o ya se usó. Vuelve a iniciar la conexión.',
  account_mismatch: 'Elegiste otra cuenta de Google. Reconecta la cuenta anterior o desconéctala primero para cambiarla.',
  scope_denied: 'Google no concedió el permiso de archivos solicitado. Vuelve a conectar.',
  reauth_required: 'Google requiere una nueva autorización. Vuelve a conectar.',
  session_expired: 'Tu sesión terminó durante la autorización. Vuelve a conectar desde esta sesión.',
  unavailable: 'No se pudo completar la conexión con Google. Vuelve a intentarlo.',
}
function size(bytes) { return new Intl.NumberFormat('es', { maximumFractionDigits: 1 }).format(bytes / 1024 / 1024) + ' MB' }
async function listFiles() {
  if (connection.value?.status !== 'ACTIVE') { files.value = []; total.value = 0; return }
  const data = await api.driveFiles(connection.value.id, page.value)
  files.value = data.items; total.value = data.total
}
async function refresh() {
  const data = await api.driveStatus()
  configured.value = data.configured; configMessage.value = data.message
  origin.value = data.origin; connection.value = data.connection
  await listFiles()
}
async function run(action) {
  if (busy.value) return
  busy.value = true; error.value = ''
  try { await action() }
  catch (failure) {
    error.value = failure.message || 'No se pudo completar la operación.'
    try { await refresh() } catch { /* conservar el primer error */ }
  } finally { busy.value = false; loading.value = false }
}
async function connect() {
  await run(async () => {
    const data = await api.driveAuthorize()
    const url = new URL(data.authorization_url)
    if (url.origin !== 'https://accounts.google.com' || url.pathname !== '/o/oauth2/v2/auth') throw new Error('Dirección de autorización no válida.')
    window.location.assign(url.href)
  })
}
async function pick() {
  await run(async () => {
    await loadPickerLibrary()
    if (controller.signal.aborted) return
    const settings = await api.drivePicker(connection.value.id)
    const ids = await chooseDriveFiles(settings, controller.signal)
    if (!ids.length || controller.signal.aborted) { message.value = 'Selección cancelada.'; return }
    await api.driveSelect(connection.value.id, ids)
    page.value = 1
    await listFiles()
    message.value = 'Selección guardada y acceso comprobado con tu cuenta de Google.'
  })
  pickerButton.value?.focus()
}
async function verify(file) {
  await run(async () => { await api.driveSelect(connection.value.id, [file.file_id]); await listFiles(); message.value = 'Google confirmó el acceso a este archivo.' })
}
async function remove(file) {
  await run(async () => { await api.driveRemove(connection.value.id, file.id); await listFiles(); message.value = 'Selección retirada. El archivo permanece en Drive.' })
}
async function disconnect() {
  await run(async () => {
    const data = await api.driveDisconnect(connection.value.id)
    confirmDisconnect.value = false
    message.value = data.revoked ? 'Google Drive desconectado. Tus archivos originales permanecen en Drive.' : 'Conexión bloqueada. Reintenta para confirmar la revocación en Google.'
    await refresh()
  })
}
async function changePage(delta) { await run(async () => { page.value += delta; await listFiles() }) }
onMounted(async () => {
  const outcome = typeof route.query.google === 'string' ? route.query.google : ''
  if (outcomes[outcome]) message.value = outcomes[outcome]
  if (outcome) await router.replace({ name: 'conexiones', query: {} })
  await run(refresh)
})
onBeforeUnmount(() => controller.abort())
</script>

<style scoped>
.drive-primary, .drive-secondary { padding: .75rem 1rem; border-radius: .6rem; min-height: 44px; font-weight: 600; }
.drive-primary { background: #2dd4bf; color: #042f2e; }
.drive-secondary { border: 1px solid #64748b; color: #e2e8f0; }
button:disabled { opacity: .5; cursor: not-allowed; }
button:focus-visible, a:focus-visible { outline: 3px solid #5eead4; outline-offset: 3px; }
</style>
