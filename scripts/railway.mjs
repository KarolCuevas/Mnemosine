// Resolve the native CLI explicitly so Railway's SDK version check also works on Windows.
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const binary = fileURLToPath(new URL(
  `../node_modules/@railway/cli/bin/railway${process.platform === 'win32' ? '.exe' : ''}`,
  import.meta.url,
));
const result = spawnSync(binary, process.argv.slice(2), {
  stdio: 'inherit',
  env: { ...process.env, _: binary },
});
if (result.error) {
  console.error('No se pudo ejecutar Railway. Instala las herramientas con npm ci.');
}
process.exit(result.status ?? 1);
