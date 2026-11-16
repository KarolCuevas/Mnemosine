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

export const api = {
  health: () => request('/api/health'),
  me: () => request('/api/auth/me'),
  login: (identity, password) => request('/api/auth/login', { method: 'POST', body: { identity, password } }),
  register: (payload) => request('/api/auth/register', { method: 'POST', body: payload }),
  logout: () => request('/api/auth/logout', { method: 'POST' })
}
