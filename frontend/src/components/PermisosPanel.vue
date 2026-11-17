<template>
  <section class="mt-6 rounded-xl border border-slate-800 bg-slate-900/50 p-4" aria-labelledby="permisos-titulo">
    <h2 id="permisos-titulo" class="text-sm font-semibold uppercase tracking-wider text-slate-300">Permisos de esta copia</h2>

    <p v-if="loading" class="mt-3 text-sm text-slate-400">Cargando permisos…</p>
    <p v-else-if="error" role="alert" class="mt-3 rounded-lg border border-red-900 bg-red-950/60 px-3 py-2 text-sm text-red-300">{{ error }}</p>

    <template v-else-if="summary">
      <p class="mt-3 text-sm text-slate-400">
        Visibilidad: <span class="font-medium text-slate-100">{{ summary.visibility === 'PUBLIC' ? 'Pública' : 'Privada' }}</span>
        · Descarga pública: <span class="font-medium text-slate-100">{{ summary.public_download_allowed ? 'Autorizada' : 'No autorizada' }}</span>
      </p>

      <!-- Publicar / despublicar -->
      <div class="mt-4">
        <template v-if="summary.visibility === 'PRIVATE'">
          <label class="mb-1 block text-xs font-medium text-slate-400" for="pub-decl">Publicar: declaración de autorización</label>
          <textarea id="pub-decl" v-model="publishDeclaration" rows="2" maxlength="500"
            placeholder="Quién declara y para qué (p. ej. 'Declaro que tengo autorización para compartir esta grabación')"
            class="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm outline-none focus:border-teal-400" />
          <button type="button" class="mt-2 rounded-lg bg-teal-500 px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-teal-400 disabled:opacity-50"
            :disabled="!publishDeclaration.trim() || busy" @click="publish">Publicar (todos los usuarios autenticados podrán reproducir)</button>
        </template>
        <button v-else type="button" class="rounded-lg border border-amber-800 bg-amber-950 px-4 py-2 text-sm font-medium text-amber-300 transition hover:bg-amber-900"
          :disabled="busy" @click="unpublish">Volver a privada</button>
      </div>

      <!-- Descarga pública -->
      <div class="mt-4 border-t border-slate-800 pt-4">
        <template v-if="!summary.public_download_allowed">
          <label class="mb-1 block text-xs font-medium text-slate-400" for="dl-decl">Descarga pública: declaración de autorización</label>
          <textarea id="dl-decl" v-model="downloadDeclaration" rows="2" maxlength="500"
            placeholder="Quién declara y para qué alcance"
            class="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm outline-none focus:border-teal-400" />
          <button type="button" class="mt-2 rounded-lg bg-teal-500 px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-teal-400 disabled:opacity-50"
            :disabled="!downloadDeclaration.trim() || busy" @click="allowPublicDownload">Autorizar descarga pública</button>
        </template>
        <button v-else type="button" class="text-sm text-slate-400 underline underline-offset-2 hover:text-slate-200"
          :disabled="busy" @click="revokePublicDownload">Revocar autorización de descarga pública</button>
      </div>

      <!-- Compartir con una cuenta -->
      <div class="mt-4 border-t border-slate-800 pt-4">
        <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-400">Compartir con una cuenta</h3>
        <div class="mt-2 flex flex-wrap items-center gap-3">
          <label class="sr-only" for="share-user">Nombre de usuario</label>
          <input id="share-user" v-model="shareForm.username" autocomplete="off" maxlength="64" placeholder="usuario"
            class="w-40 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm outline-none focus:border-teal-400" />
          <label class="flex items-center gap-1.5 text-sm text-slate-300">
            <input type="checkbox" v-model="shareForm.can_stream" class="h-4 w-4 accent-teal-400" /> Reproducir
          </label>
          <label class="flex items-center gap-1.5 text-sm text-slate-300">
            <input type="checkbox" v-model="shareForm.can_download" class="h-4 w-4 accent-teal-400" /> Descargar
          </label>
        </div>
        <label class="mb-1 mt-2 block text-xs font-medium text-slate-400" for="share-decl">Declaración de autorización</label>
        <textarea id="share-decl" v-model="shareForm.declaration" rows="2" maxlength="500"
          placeholder="Quién declara, con quién y para qué alcance"
          class="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm outline-none focus:border-teal-400" />
        <button type="button" class="mt-2 rounded-lg border border-teal-800 bg-teal-950 px-4 py-2 text-sm font-medium text-teal-300 transition hover:bg-teal-900 disabled:opacity-50"
          :disabled="!shareForm.username.trim() || !shareForm.declaration.trim() || busy" @click="share">Compartir</button>

        <ul v-if="summary.shares.length" class="mt-3 divide-y divide-slate-800 rounded-lg border border-slate-800">
          <li v-for="entry in summary.shares" :key="entry.recipient_user_id" class="flex items-center justify-between gap-3 px-3 py-2 text-xs">
            <span class="min-w-0">
              <span class="font-medium text-slate-200">{{ entry.username }}</span>
              <span class="ml-2 text-slate-500">{{ entry.can_stream ? 'reproducir' : '' }}{{ entry.can_stream && entry.can_download ? ' + ' : '' }}{{ entry.can_download ? 'descargar' : '' }}</span>
              <span v-if="entry.revoked_at" class="ml-2 rounded-full border border-slate-700 px-2 py-0.5 text-[10px] uppercase text-slate-500">revocado</span>
            </span>
            <button v-if="!entry.revoked_at" type="button" class="rounded-lg border border-slate-700 px-2 py-1 text-slate-400 transition hover:border-red-800 hover:text-red-300"
              :disabled="busy" @click="revoke(entry.recipient_user_id)">Revocar</button>
          </li>
        </ul>
      </div>

      <p v-if="status" role="status" class="mt-3 text-sm text-teal-300">{{ status }}</p>
      <p v-if="actionError" role="alert" class="mt-3 text-sm text-red-300">{{ actionError }}</p>
    </template>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api, ApiError } from '../services/api'

const props = defineProps({ locationId: { type: Number, required: true } })
const emit = defineEmits(['updated'])

const summary = ref(null)
const loading = ref(true)
const error = ref('')
const busy = ref(false)
const status = ref('')
const actionError = ref('')

const publishDeclaration = ref('')
const downloadDeclaration = ref('')
const shareForm = reactive({ username: '', can_stream: true, can_download: false, declaration: '' })

async function load() {
  loading.value = true
  error.value = ''
  try {
    summary.value = await api.locationSummary(props.locationId)
  } catch (err) {
    error.value = 'No se pudieron cargar los permisos de la copia.'
  } finally {
    loading.value = false
  }
}

async function run(action, okMessage) {
  busy.value = true
  status.value = ''
  actionError.value = ''
  try {
    await action()
    status.value = okMessage
    await load()
    emit('updated')
  } catch (err) {
    if (err instanceof ApiError) actionError.value = err.message
    else actionError.value = 'No se pudo completar la acción.'
  } finally {
    busy.value = false
  }
}

const publish = () => run(() => api.setVisibility(props.locationId, { publish: true, declaration: publishDeclaration.value.trim() }), 'La copia es pública.').then(() => { publishDeclaration.value = '' })
const unpublish = () => run(() => api.setVisibility(props.locationId, { publish: false }), 'La copia vuelve a ser privada.')
const allowPublicDownload = () => run(() => api.setPublicDownload(props.locationId, { allow: true, declaration: downloadDeclaration.value.trim() }), 'Descarga pública autorizada.').then(() => { downloadDeclaration.value = '' })
const revokePublicDownload = () => run(() => api.setPublicDownload(props.locationId, { allow: false }), 'Descarga pública revocada.')
const revoke = (recipientId) => run(() => api.revokeShare(props.locationId, recipientId), 'Compartir revocado. Las nuevas solicitudes serán denegadas.')

const share = () => run(() => api.createShare(props.locationId, {
  username: shareForm.username.trim().toLowerCase(),
  can_stream: shareForm.can_stream,
  can_download: shareForm.can_download,
  declaration: shareForm.declaration.trim()
}), 'Copia compartida.').then(() => { shareForm.username = ''; shareForm.declaration = '' })

onMounted(load)
</script>
