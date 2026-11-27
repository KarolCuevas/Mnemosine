import { test, expect } from '@playwright/test'

test('referencias: búsqueda explícita, errores, colección privada y vista móvil', async ({ page }, testInfo) => {
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  let saved = [], remoteCalls = 0, failNext = false
  const item = {
    provider: 'musicbrainz', entity_type: 'recording', provider_id: '11111111-1111-4111-8111-111111111111',
    title: 'Clair de lune', artists: [{ name: 'Claude Debussy', credit: 'Claude Debussy', join_phrase: '' }],
    duration_ms: 297000, releases: [{ provider_id: '22222222-2222-4222-8222-222222222222', title: 'Suite bergamasque', date: '2020' }],
    isrcs: [], disambiguation: 'piano solo', original_url: 'https://musicbrainz.org/recording/11111111-1111-4111-8111-111111111111',
    fetched_at: '2026-11-25T00:00:00Z',
  }
  await page.route('**/api/integrations/providers', route => route.fulfill({ json: { items: [{ code: 'musicbrainz', enabled: true }] } }))
  await page.route('**/api/catalog/recordings?**', route => route.fulfill({ json: { items: [], total: 0, origin: 'local' } }))
  await page.route('**/api/external/**', async route => {
    const request = route.request(), url = new URL(request.url())
    if (url.pathname.endsWith('/search')) {
      remoteCalls++
      if (failNext) { failNext = false; return route.fulfill({ status: 429, headers: { 'Retry-After': '2' }, json: { detail: 'Proveedor ocupado.' } }) }
      return route.fulfill({ json: { items: [item], total: 1, origin: 'provider', next_cursor: null } })
    }
    if (request.method() === 'POST') { saved = [{ ...item, reference_id: 7 }]; return route.fulfill({ status: 201, json: saved[0] }) }
    if (request.method() === 'DELETE') { saved = []; return route.fulfill({ status: 204 }) }
    return route.fulfill({ json: { items: saved, total: saved.length, page: 1, page_size: 20 } })
  })
  await page.goto('/acceso')
  await page.getByLabel('Usuario o correo').fill(process.env.E2E_IDENTITY ?? 'e2e_admin')
  await page.getByLabel('Contraseña').fill(process.env.E2E_PASSWORD ?? 'e2e-demo-password-2026!')
  await page.getByRole('button', { name: 'Entrar' }).click()
  await page.getByRole('link', { name: 'Referencias musicales' }).click()
  await expect(page.getByRole('heading', { name: 'Referencias musicales' })).toBeVisible()
  await expect(page.getByText('No hay coincidencias en el índice.', { exact: false })).toBeVisible()
  await page.getByRole('radio', { name: 'MusicBrainz', exact: true }).check()
  expect(remoteCalls).toBe(0)
  await page.getByLabel('Título (obligatorio)').fill('Clair de lune')
  await page.getByLabel('Artista (opcional)').fill('Claude Debussy')
  await page.getByRole('button', { name: 'Buscar', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Clair de lune' })).toBeVisible()
  await expect(page.getByRole('main').getByRole('button', { name: /Reproducir|Descargar/ })).toHaveCount(0)
  await expect(page.getByText('Nada en reproducción')).toHaveCount(0)
  await expect(page.getByRole('link', { name: /Ver Clair de lune en MusicBrainz/ })).toHaveAttribute('href', item.original_url)
  await page.screenshot({ path: testInfo.outputPath('references-desktop.png'), fullPage: true })
  await page.getByRole('button', { name: 'Guardar referencia: Clair de lune' }).click()
  await expect(page.getByRole('status')).toContainText('guardada en tu colección privada')
  await page.getByRole('radio', { name: 'Mi colección privada', exact: true }).check()
  await page.getByRole('button', { name: 'Ver mi colección' }).click()
  await expect(page.getByRole('heading', { name: 'Clair de lune' })).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: testInfo.outputPath('references-mobile.png'), fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.getByRole('button', { name: 'Quitar de mi colección: Clair de lune' }).click()
  await expect(page.getByText('Todavía no has guardado referencias.')).toBeVisible()
  failNext = true
  await page.getByRole('radio', { name: 'MusicBrainz', exact: true }).check()
  await page.getByRole('button', { name: 'Buscar', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('2 segundos')
  await page.getByRole('button', { name: 'Buscar', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Clair de lune' })).toBeVisible()
  expect(errors).toEqual([])
})
