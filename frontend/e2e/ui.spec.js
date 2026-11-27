import { test, expect } from '@playwright/test'

// Synthetic responses keep layout and interaction checks independent of private music/accounts.
const sampleTracks = [
  ['Un recuerdo que dura para siempre', 'Clara del Mar', 'Horizontes'],
  ['Brisa de la tarde', 'Clara del Mar', 'Horizontes'],
  ['La ciudad despierta', 'Los Días Lentos', 'Entre luces'],
  ['Cerca del sol', 'Elena Ríos', 'Días de verano'],
  ['Una vuelta más', 'Los Días Lentos', 'Entre luces'],
  ['Cuando todo está en calma', 'Nicolás Sierra', 'Pausa'],
  ['Domingo en casa', 'Elena Ríos', 'Días de verano'],
  ['El último tren', 'Nicolás Sierra', 'Pausa'],
].map(([title, artists, album], index) => ({ track_id: index + 1, location_id: index + 1, title, artists, album, duration_seconds: 180 + index * 21, available: true }))

function silentAudio() {
  const rate = 8000, length = rate * 60 * 2, buffer = Buffer.alloc(44 + length)
  buffer.write('RIFF'); buffer.writeUInt32LE(36 + length, 4); buffer.write('WAVEfmt ', 8)
  buffer.writeUInt32LE(16, 16); buffer.writeUInt16LE(1, 20); buffer.writeUInt16LE(1, 22)
  buffer.writeUInt32LE(rate, 24); buffer.writeUInt32LE(rate * 2, 28); buffer.writeUInt16LE(2, 32); buffer.writeUInt16LE(16, 34)
  buffer.write('data', 36); buffer.writeUInt32LE(length, 40)
  return buffer
}

async function mockApp(page, { signedIn = true, tracks = sampleTracks, failLibrary = false } = {}) {
  const state = { signedIn, failLibrary, uploaded: false, created: null, searches: [] }
  const user = { id: 1, username: 'valentina', display_name: 'Valentina', role: 'ADMIN' }
  const playlists = [{ playlist_id: 1, name: 'Domingos sin prisa', description: 'Para bajar el ritmo y disfrutar el momento.', item_count: 4 }]
  const wav = silentAudio()
  await page.route('**/api/**', async route => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname
    const json = data => route.fulfill({ json: data })
    if (path === '/api/auth/me') return state.signedIn ? json(user) : route.fulfill({ status: 401, json: { detail: 'Sin sesión' } })
    if (path === '/api/auth/login' || path === '/api/auth/register') { state.signedIn = true; return json(user) }
    if (path === '/api/auth/logout') { state.signedIn = false; return route.fulfill({ status: 204 }) }
    if (path === '/api/library') {
      if (state.failLibrary) { state.failLibrary = false; return route.fulfill({ status: 503, json: { detail: 'Sin conexión' } }) }
      const q = (url.searchParams.get('q') || '').toLocaleLowerCase('es')
      state.searches.push(q)
      const items = tracks.filter(item => `${item.title} ${item.artists} ${item.album}`.toLocaleLowerCase('es').includes(q))
      return json({ items, total: items.length, page: 1, page_size: 24 })
    }
    if (path === '/api/library/shared') return json({ items: [] })
    if (path === '/api/tracks/upload') { state.uploaded = true; return json({ ...tracks[1], size_bytes: wav.length }) }
    if (/\/tracks\/\d+\/audio$/.test(path)) return route.fulfill({ contentType: 'audio/wav', body: wav })
    if (/\/tracks\/\d+$/.test(path)) {
      const track = tracks.find(item => item.track_id === Number(path.split('/').at(-1))) || sampleTracks[1]
      return json({ ...track, access: { can_stream: true, can_download: true }, copies: [{ location_id: track.location_id, visibility: 'PRIVATE', availability: 'AVAILABLE', size_bytes: 4200000, mime_type: 'audio/mpeg', sha256: 'a'.repeat(64) }] })
    }
    if (/\/locations\/\d+$/.test(path)) return json({ visibility: 'PRIVATE', public_download_allowed: false, shares: [] })
    if (path === '/api/playlists' && request.method() === 'POST') { state.created = request.postDataJSON().name; return json({ playlist_id: 1 }) }
    if (path === '/api/playlists') return json(playlists)
    if (path === '/api/playlists/1') return json({ ...playlists[0], name: state.created || playlists[0].name, tracks: tracks.slice(0, 4) })
    if (path === '/api/discovery') return json({ accounts: [{ username: 'sofia', display_name: 'Sofía', public_copies: 8 }, { username: 'andres', display_name: 'Andrés', public_copies: 12 }] })
    if (path.startsWith('/api/discovery/')) return json({ items: tracks })
    if (path === '/api/integrations/providers') return json({ items: [{ code: 'musicbrainz', enabled: true }] })
    if (path === '/api/catalog/recordings' || path === '/api/external/references') return json({ items: [], total: 0, origin: 'local' })
    if (path === '/api/admin/users') return json([{ ...user, email: 'valentina@ejemplo.test', is_active: true }, { id: 2, username: 'usuario_con_nombre_muy_largo', email: 'un.correo.largo.para.probar.el.diseno@ejemplo.test', role: 'USER', is_active: true }])
    if (path === '/api/admin/sources') return json([])
    if (path === '/api/admin/operations' || path === '/api/admin/permission-audit') return json({ items: [], total: 0, page: 1, page_size: 25 })
    return route.fulfill({ status: 404, json: { detail: `No fixture for ${path}` } })
  })
  return state
}

async function expectContained(page) {
  const sizes = await page.evaluate(() => {
    const main = document.querySelector('main')
    return { document: document.documentElement.scrollWidth, viewport: innerWidth, main: main?.scrollWidth, available: main?.clientWidth }
  })
  expect(sizes.document).toBeLessThanOrEqual(sizes.viewport + 1)
  expect(sizes.main).toBeLessThanOrEqual(sizes.available + 1)
  const player = page.getByRole('region', { name: 'Reproductor de música' })
  if (await player.count()) {
    const mainBox = await page.getByRole('main').boundingBox(), playerBox = await player.boundingBox()
    expect(mainBox.y + mainBox.height).toBeLessThanOrEqual(playerBox.y + 1)
  }
}

for (const [width, height] of [[320, 740], [390, 844], [768, 1024], [1024, 768], [1440, 900], [1920, 1080], [2560, 1440]]) {
  test(`pantallas sin desbordamiento ni reproductor superpuesto a ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height })
    await mockApp(page)
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    for (const route of ['/biblioteca', '/biblioteca/cargar', '/listas', '/listas/1', '/descubrir', '/descubrir/sofia', '/referencias', '/cancion/2', '/admin']) {
      await page.goto(route)
      await expect(page.getByRole('main')).toBeVisible()
      await expect(page.locator('.page h1')).toBeVisible()
      if (route === '/admin') await expect(page.getByRole('cell', { name: 'valentina@ejemplo.test', exact: true })).toBeVisible()
      await expectContained(page)
      if (width >= 768) await expect(page.getByRole('button', { name: 'Abrir navegación' })).toBeHidden()
      if (route === '/biblioteca') {
        await expect(page.locator('.track-item')).toHaveCount(8)
        if (width >= 1440) expect((await page.locator('.library-hero').boundingBox()).width).toBeGreaterThan(width * .7)
        await page.screenshot({ path: testInfo.outputPath(`biblioteca-${width}.png`) })
      }
      if ([390, 1440].includes(width) && route !== '/biblioteca') await page.screenshot({ path: testInfo.outputPath(`${route.slice(1).replaceAll('/', '-')}-${width}.png`) })
    }
    expect(errors).toEqual([])
  })
}

test('navegación móvil con teclado, lista, búsqueda y tarjetas', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const state = await mockApp(page)
  await page.goto('/biblioteca')
  await page.getByRole('button', { name: 'Abrir navegación' }).focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('button', { name: 'Cerrar navegación' })).toHaveAttribute('aria-expanded', 'true')
  await page.getByRole('navigation', { name: 'Principal', exact: true }).getByRole('link', { name: 'Mis listas', exact: true }).click()
  await expect(page).toHaveURL(/\/listas$/)
  await expect(page.getByRole('button', { name: 'Abrir navegación' })).toHaveAttribute('aria-expanded', 'false')
  await expect(page.getByRole('main')).toBeFocused()
  await page.getByLabel('Nombre de la nueva lista').fill('Para viajar')
  await page.getByRole('button', { name: 'Crear lista', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Para viajar' })).toBeVisible()
  expect(state.created).toBe('Para viajar')
  await page.goto('/biblioteca')
  await page.getByRole('button', { name: 'Vista de cuadrícula' }).click()
  await expect(page.locator('.track-grid')).toBeVisible()
  await expectContained(page)
  await page.getByLabel('Buscar en tu biblioteca').fill('Elena')
  await expect(page.locator('.track-item')).toHaveCount(2)
  await page.getByLabel('Buscar en tu biblioteca').fill('Nada que exista')
  await expect(page.getByRole('heading', { name: 'No encontramos esa canción' })).toBeVisible()
  await page.getByRole('button', { name: 'Limpiar búsqueda', exact: true }).first().click()
  await expect(page.locator('.track-item')).toHaveCount(8)
})

test('reproduce la canción elegida, persiste al navegar y se detiene al salir', async ({ page }) => {
  const tracks = structuredClone(sampleTracks)
  tracks[0].available = false
  await mockApp(page, { tracks })
  await page.goto('/biblioteca')
  await page.getByRole('button', { name: 'Reproducir Brisa de la tarde', exact: true }).click()
  const player = page.getByRole('region', { name: 'Reproductor de música' })
  await expect(player.getByRole('link', { name: 'Brisa de la tarde', exact: true })).toBeVisible()
  await expect(player.getByRole('button', { name: 'Pausar', exact: true })).toBeVisible()
  await page.getByRole('navigation', { name: 'Principal', exact: true }).getByRole('link', { name: 'Referencias musicales', exact: true }).click()
  await expect(player.getByRole('button', { name: 'Pausar', exact: true })).toBeVisible()
  await player.getByRole('button', { name: 'Siguiente', exact: true }).click()
  await expect(player.getByRole('link', { name: 'La ciudad despierta', exact: true })).toBeVisible()
  await page.getByRole('navigation', { name: 'Principal', exact: true }).getByRole('link', { name: 'Mi biblioteca', exact: true }).click()
  await page.getByRole('main').getByRole('link', { name: 'Brisa de la tarde Clara del Mar' }).click()
  await expect(page.getByRole('heading', { name: 'Brisa de la tarde', exact: true })).toBeVisible()
  await player.getByRole('link', { name: 'La ciudad despierta', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'La ciudad despierta', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Cerrar sesión' }).click()
  await expect(page).toHaveURL(/\/acceso$/)
  await expect(player).toHaveCount(0)
  await page.getByLabel('Usuario o correo').fill('valentina')
  await page.getByLabel('Contraseña', { exact: true }).fill('una-contraseña-de-prueba')
  await page.getByRole('button', { name: 'Entrar', exact: true }).click()
  await expect(player.getByText('Tu próxima canción te espera')).toBeVisible()
  await expect(player.getByRole('button', { name: 'Reproducir', exact: true })).toBeDisabled()
})

test('acceso, registro y subida en móvil', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const state = await mockApp(page, { signedIn: false })
  await page.goto('/')
  await expect(page).toHaveURL(/\/acceso/)
  await expectContained(page)
  await page.screenshot({ path: testInfo.outputPath('acceso-mobile.png'), fullPage: true })
  await page.getByRole('button', { name: 'Crear cuenta', exact: true }).click()
  await page.getByLabel('Usuario', { exact: true }).fill('valentina')
  await page.getByLabel('Correo', { exact: true }).fill('valentina@ejemplo.test')
  await page.getByLabel('Código de invitación').fill('invitacion-de-prueba')
  await page.getByLabel('Contraseña', { exact: true }).fill('una-contraseña-de-prueba')
  await page.getByRole('button', { name: 'Crear cuenta e iniciar sesión', exact: true }).click()
  await expect(page).toHaveURL(/\/biblioteca$/)
  await page.getByRole('main').getByRole('link', { name: 'Subir música', exact: true }).click()
  await page.getByLabel('Archivo de audio').setInputFiles({ name: 'Brisa de la tarde.wav', mimeType: 'audio/wav', buffer: silentAudio() })
  await page.getByLabel('Artista', { exact: true }).fill('Clara del Mar')
  await page.getByRole('button', { name: 'Guardar como privada' }).click()
  await expect(page.getByRole('status')).toContainText('subida correctamente')
  expect(state.uploaded).toBe(true)
  await expectContained(page)
})

test('errores recuperables y biblioteca vacía tienen acciones útiles', async ({ page }, testInfo) => {
  await mockApp(page, { tracks: [], failLibrary: true })
  await page.goto('/biblioteca')
  await expect(page.getByRole('alert')).toContainText('No se pudo cargar la biblioteca')
  await page.getByRole('button', { name: 'Volver a intentar' }).click()
  await expect(page.getByRole('heading', { name: 'Tu colección empieza aquí' })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('biblioteca-vacia.png') })
  await page.getByRole('link', { name: 'Subir mi primera canción' }).click()
  await expect(page).toHaveURL(/\/biblioteca\/cargar$/)
})
