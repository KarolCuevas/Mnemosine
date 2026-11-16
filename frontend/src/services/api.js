const CSRF_COOKIE = 'mnemosine_csrf'

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function readCookie(name) {
  const prefix = `${name}=`
  const found = document.cookie.split('; ').find((entry) => entry.startsWith(prefix))
  return found ? decodeURIComponent(found.slice(prefix.length)) : null
}

async function request(path, { method = 'GET', body } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (method !== 'GET') {
    const csrf = readCookie(CSRF_COOKIE)
    if (csrf) headers['X-CSRF-Token'] = csrf
  }
  const response = await fetch(path, {
    method,
    headers,
    credentials: 'same-origin',
    body: body !== undefined ? JSON.stringify(body) : undefined
  })
  let data = null
  try {
    data = await response.json()
  } catch {
    data = null
  }
  if (!response.ok) {
    throw new ApiError(response.status, data?.detail ?? 'No se pudo completar la solicitud')
  }
  return data
}

export function uploadWithProgress(formData, { onProgress } = {}) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/tracks/upload')
    xhr.withCredentials = true
    const csrf = readCookie(CSRF_COOKIE)
    if (csrf) xhr.setRequestHeader('X-CSRF-Token', csrf)

    xhr.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable && typeof onProgress === 'function') {
        onProgress(Math.round((event.loaded / event.total) * 100))
      }
    })
    xhr.addEventListener('load', () => {
      let data = null
      try {
        data = JSON.parse(xhr.responseText)
      } catch {
        data = null
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(data)
      } else {
        reject(new ApiError(xhr.status, data?.detail ?? 'No se pudo subir el archivo'))
      }
    })
    xhr.addEventListener('error', () => reject(new ApiError(0, 'Error de red al subir el archivo')))
    xhr.addEventListener('abort', () => reject(new ApiError(0, 'Subida cancelada')))
    xhr.send(formData)
  })
}

export const api = {
  health: () => request('/api/health'),
  me: () => request('/api/auth/me'),
  login: (identity, password) => request('/api/auth/login', { method: 'POST', body: { identity, password } }),
  register: (payload) => request('/api/auth/register', { method: 'POST', body: payload }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  library: ({ q = '', page = 1, pageSize = 24 } = {}) => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
    if (q) params.set('q', q)
    return request(`/api/library?${params.toString()}`)
  },
  getTrack: (id) => request(`/api/tracks/${id}`),
  audioUrl: (id) => `/api/tracks/${id}/audio`,
  downloadUrl: (id) => `/api/tracks/${id}/download`
}
