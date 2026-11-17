import { test, expect } from '@playwright/test'

const IDENTITY = process.env.E2E_IDENTITY ?? 'e2e_admin'
const PASSWORD = process.env.E2E_PASSWORD ?? 'e2e-demo-password-2026!'

test('la app carga, redirige a /acceso, abre sesión y cierra sesión', async ({ page }) => {
  const pageErrors = []
  page.on('pageerror', (error) => pageErrors.push(error.message))

  await page.goto('/')
  await expect(page).toHaveURL(/\/acceso/)
  await expect(page.getByRole('heading', { name: 'Tu música, tuya' })).toBeVisible()

  await page.getByLabel('Usuario o correo').fill(IDENTITY)
  await page.getByLabel('Contraseña').fill(PASSWORD)
  await page.getByRole('button', { name: 'Entrar' }).click()

  await expect(page).toHaveURL(/\/biblioteca$/)
  await expect(page.getByRole('heading', { name: 'Tus canciones' })).toBeVisible()

  await page.getByRole('button', { name: 'Cerrar sesión' }).click()
  await expect(page).toHaveURL(/\/acceso$/)

  expect(pageErrors).toEqual([])
})
