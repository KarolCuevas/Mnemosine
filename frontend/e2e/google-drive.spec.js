import { test, expect } from '@playwright/test'

test('Drive: selector explícito, selección privada, cancelación y desconexión', async ({ page }, testInfo) => {
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  let sdkLoads = 0, tokenCalls = 0, selected = [], status = 'ACTIVE', failNext = false
  const origin = new URL(process.env.PLAYWRIGHT_BASE_URL ?? 'http://127.0.0.1:5174').origin
  await page.route('https://apis.google.com/js/api.js', async route => {
    sdkLoads++
    await route.fulfill({ contentType: 'application/javascript', body: `
      window.gapi = { load: (name, options) => options.callback() };
      window.google = { picker: {
        Action: { CANCEL: 'cancel', PICKED: 'picked' }, ViewId: { DOCS: 'docs' }, DocsViewMode: { LIST: 'list' },
        DocsView: class { setIncludeFolders(){return this} setSelectFolderEnabled(){return this} setOwnedByMe(){return this} setMode(){return this} setMimeTypes(){return this} },
        PickerBuilder: class {
          addView(){return this} setAppId(){return this} setDeveloperKey(){return this}
          setOAuthToken(){return this} setOrigin(){return this} setTitle(){return this}
          setCallback(fn){this.callback=fn;return this}
          build(){ return { dispose: () => {}, setVisible: () => queueMicrotask(() => this.callback({ action:'picked', docs:[{id:'file_a',name:'UNTRUSTED'}] })) } }
        }
      }};
    ` })
  })
  await page.route('**/api/integrations/google_drive/**', async route => {
    const request = route.request(), path = new URL(request.url()).pathname
    if (path.endsWith('/status')) return route.fulfill({ json: { configured: true, origin, connection: { id: 1, status, email: 'piloto@example.test' } } })
    if (path.endsWith('/picker')) {
      tokenCalls++
      return route.fulfill({ headers: { 'Cache-Control': 'private, no-store' }, json: { access_token: 'TEMP_TOKEN_TEST', developer_key: 'TEST_KEY', app_id: '123', origin } })
    }
    if (path.endsWith('/disconnect')) { status = 'DISCONNECTED'; selected = []; return route.fulfill({ json: { revoked: true } }) }
    if (request.method() === 'DELETE') { selected = []; return route.fulfill({ status: 204 }) }
    if (request.method() === 'POST' && path.endsWith('/files')) {
      expect(request.postDataJSON()).toEqual({ file_ids: ['file_a'] })
      if (failNext) { failNext = false; status = 'REAUTH_REQUIRED'; return route.fulfill({ status: 409, json: { detail: 'Vuelve a conectar tu Drive.' } }) }
      selected = [{ id: 1, file_id: 'file_a', name: 'Audio <privado>.wav', size_bytes: 1234, audio_validated: false }]
      return route.fulfill({ json: { items: selected } })
    }
    return route.fulfill({ json: { items: selected, total: selected.length, page: 1, page_size: 25 } })
  })
  await page.goto('/acceso')
  await page.getByLabel('Usuario o correo').fill(process.env.E2E_IDENTITY ?? 'e2e_admin')
  await page.getByLabel('Contraseña').fill(process.env.E2E_PASSWORD ?? 'e2e-demo-password-2026!')
  await page.getByRole('button', { name: 'Entrar' }).click()
  await page.getByRole('link', { name: 'Mi Google Drive', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Mi Google Drive', exact: true })).toBeVisible()
  expect(sdkLoads).toBe(0)
  expect(tokenCalls).toBe(0)
  await page.getByRole('button', { name: 'Elegir un audio de Drive' }).click()
  await expect(page.getByRole('heading', { name: 'Audio <privado>.wav' })).toBeVisible()
  expect(sdkLoads).toBe(1)
  expect(tokenCalls).toBe(1)
  await expect(page.getByText('UNTRUSTED')).toHaveCount(0)
  expect(await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }))).not.toContain('TEMP_TOKEN_TEST')
  await expect(page.getByRole('main').getByRole('button', { name: /Reproducir|Descargar/ })).toHaveCount(0)
  await page.screenshot({ path: testInfo.outputPath('drive-desktop.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('drive-mobile.png'), fullPage: true })
  await page.getByRole('button', { name: 'Desconectar Google Drive', exact: true }).click()
  await page.getByRole('button', { name: 'Cancelar', exact: true }).click()
  await expect(page.getByText('Conectada', { exact: true })).toBeVisible()
  failNext = true
  await page.getByRole('button', { name: 'Comprobar acceso: Audio <privado>.wav' }).click()
  await expect(page.getByRole('alert')).toContainText('Vuelve a conectar')
  await expect(page.getByRole('button', { name: 'Reconectar Google Drive' })).toBeVisible()
  await page.getByRole('button', { name: 'Desconectar Google Drive', exact: true }).click()
  await page.getByRole('button', { name: 'Confirmar desconexión' }).click()
  await expect(page.getByText('Sin conexión', { exact: true })).toBeVisible()
  expect(errors).toEqual([])
})
