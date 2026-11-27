// Se carga solo al pulsar Elegir. Las credenciales viven únicamente en esta llamada.
let libraryPromise

export function loadPickerLibrary() {
  if (window.google?.picker) return Promise.resolve()
  if (libraryPromise) return libraryPromise
  libraryPromise = new Promise((resolve, reject) => {
    let script, timer
    const fail = () => {
      clearTimeout(timer)
      script?.remove()
      reject(new Error('No se pudo cargar el selector de Google. Revisa tu conexión y vuelve a intentarlo.'))
    }
    const loaded = () => {
      window.gapi.load('picker', {
        callback: () => { clearTimeout(timer); resolve() },
        onerror: fail,
        timeout: 15000,
        ontimeout: fail,
      })
    }
    timer = setTimeout(fail, 20000)
    if (window.gapi?.load) loaded()
    else {
      script = document.createElement('script')
      // URL fija, sin parámetros ni contenido del usuario. Google actualiza este recurso.
      script.src = 'https://apis.google.com/js/api.js'
      script.async = true
      script.referrerPolicy = 'strict-origin-when-cross-origin'
      script.onload = loaded
      script.onerror = fail
      document.head.append(script)
    }
  }).catch(error => { libraryPromise = undefined; throw error })
  return libraryPromise
}

export function chooseDriveFiles(settings, signal) {
  return new Promise((resolve, reject) => {
    let picker, finished = false
    const finish = (ids = [], error = null) => {
      if (finished) return
      finished = true
      signal?.removeEventListener('abort', cancelled)
      picker?.dispose()
      picker = null
      settings.access_token = ''
      if (error) reject(error)
      else resolve(ids)
    }
    const cancelled = () => finish([])
    if (signal?.aborted) return finish([])
    if (settings.origin !== window.location.origin) {
      return finish([], new Error('Abre Mnemosine desde la dirección configurada para conectar Google.'))
    }
    try {
      const googlePicker = window.google.picker
      const view = new googlePicker.DocsView(googlePicker.ViewId.DOCS)
        .setIncludeFolders(false).setSelectFolderEnabled(false).setOwnedByMe(true)
        .setMode(googlePicker.DocsViewMode.LIST)
        .setMimeTypes('audio/mpeg,audio/mp4,audio/aac,audio/flac,audio/x-flac,audio/ogg,application/ogg,audio/wav,audio/x-wav')
      picker = new googlePicker.PickerBuilder()
        .addView(view).setAppId(settings.app_id).setDeveloperKey(settings.developer_key)
        .setOAuthToken(settings.access_token).setOrigin(settings.origin)
        .setTitle('Elegir un audio de mi Drive')
        .setCallback(data => {
          if (data.action === googlePicker.Action.CANCEL) finish([])
          if (data.action === googlePicker.Action.PICKED) {
            const ids = (data.docs ?? []).map(doc => doc.id).filter(id => typeof id === 'string')
            finish(ids.slice(0, 5))
          }
        }).build()
      signal?.addEventListener('abort', cancelled, { once: true })
      picker.setVisible(true)
    } catch {
      finish([], new Error('No se pudo abrir el selector de Google. Vuelve a conectar tu Drive si el problema continúa.'))
    }
  })
}
