# Bocetos del recorrido principal (Fase 0 / H3) — Mnemosine

Fecha: 16 de noviembre de 2026. Estado: bocetos de baja fidelidad (markdown);
no son diseño gráfico final. Pantallas: acceso, biblioteca, carga, detalle,
permisos básicos, reproductor persistente.

Convención: `[ ... ]` botón/acción, `( )` campo, `‖◁▶‖` control de audio,
`···` menú contextual. Cada pantalla indica sus **estados vacíos y errores**.

## 1. Acceso — `/acceso`

```text
┌─────────────────────────────────────────┐
│              M N E M O S I N E          │
│   Tu biblioteca. Tuya.                  │
│                                         │
│   (Usuario o correo)                    │
│   (Contraseña)                          │
│                                         │
│   [ Iniciar sesión ]                    │
│   ¿Invitación? → [ Crear cuenta ]       │
└─────────────────────────────────────────┘
```
Crear cuenta pide `(Código de invitación)`. Errores: credenciales inválidas
(mensaje único, no revela si la cuenta existe), invitación caducada/usada,
429 con reintento más tarde. Sin sesión previa, cualquier ruta → `/acceso`.

## 2. Mi biblioteca — `/biblioteca`

```text
┌────────────────────────────────────────────────┐
│ Mnemosine        Buscar (título/artista/álbum) │
│ [+ Cargar]                          [A][Cuenta]│
├────────────────────────────────────────────────┤
│ ▣ Aurora — Kältmare          ▶  ⬇  ⋮           │
│ ▣ Neon Tides — Aya Duarte    ▶  ⬇  ⋮           │
│ …paginada (Anterior · 1 2 3 · Siguiente)…      │
├────────────────────────────────────────────────┤
│ ‖◁▶▷  Aurora — Kältmare          0:42 / 3:18   │  ← reproductor persistente
└────────────────────────────────────────────────┘
```
Estados vacíos: biblioteca sin cargas → explicación + `[Cargar tu primera
canción]`. Búsqueda sin resultados → «Nada por “…”» + limpiar filtro. Errores:
401 → redirige a acceso; 500 → aviso con reintentar. Lista vacía no muestra
reproductor.

## 3. Carga — `/biblioteca/cargar`

```text
┌──────────────────────────────────────┐
│ Cargar canción (privada por defecto) │
│                                      │
│  (…seleccionar archivo…)  [Elegir]   │
│  Título (……)  Artista (……)           │
│  Álbum (……)   Pista (…) Nº (…)       │
│                                      │
│  ▓▓▓▓▓▓▓▓░░░░░░░  62%  [Cancelar]     │
│                                      │
│  [ Guardar ]                         │
└──────────────────────────────────────┘
```
Errores: formato no admitido (lista los admitidos), archivo > 50 MB,
tipo falsificado (extensión ≠ contenido), fallo de disco/transacción →
«No se guardó; inténtalo de nuevo» (compensación automática, sin referencias
huérfanas visibles). Éxito → redirige al detalle con etiqueta «Privada».

## 4. Detalle de canción — `/cancion/:id`

```text
┌──────────────────────────────────────┐
│  ▶  Aurora — Kältmare · álbum «Sol»  │
│  Duración 3:18 · MP3 · 7.4 MB        │
│  Copia: mi biblioteca · Privada ✓    │
│                                      │
│  [Reproducir] [Descargar]            │
│  [Permisos…]           [Añadir a lista (H4)] │
└──────────────────────────────────────┘
```
Errores: ID inexistente o sin permiso → **404** (mismo mensaje; no revela
existencia). Copia MISSING → «No disponible: el archivo falta en la fuente»;
no ofrece reproducir ni descargar; la canción permanece en la biblioteca.

## 5. Permisos de la copia — `/cancion/:id/permisos`

```text
┌──────────────────────────────────────┐
│ Permisos de «Aurora — Kältmare»      │
│ Visibilidad: (•) Privada  ( ) Pública│
│ ☐ Declaro que tengo autorización…    │  ← PUBLICATION asociada a la copia
│ ☐ Autorizo la descarga pública de esta copia│ ← DOWNLOAD asociada a la copia
│                                      │
│ Compartida con:                      │
│  B  ☑ Reproducir  ☐ Descargar  [↺]   │
│  [+ Compartir con otra cuenta…]      │
└──────────────────────────────────────┘
```
H3 solo implementa visibilidad y permisos propios sobre la copia; el bloque
«Compartida con» es esqueleto hasta H4. Toda mutación exige CSRF y queda en
PERMISSION_AUDIT (H4) / FILE_OPERATION. Errores: desmarcar la declaración
deshabilita publicar/descargar-ajeno.

## 6. Reproductor persistente (en todas las vistas autenticadas)

```text
┌───────────────────────────────────────────────────┐
│ ⏮ ‖◁ ▶/⏸ ▷ ⏭   Título — Artista   ━━━●━━  1:02/3:18 │
│ Volumen (━━●)   cola: siguiente «Neon Tides»       │
└───────────────────────────────────────────────────┘
```
Requisito técnico: `<audio>` con `src` a `/api/tracks/{id}/audio` (nunca
ruta física); `Range` gestionado por el navegador; cada petición (también
rangos) revalida sesión y permiso. Pause/seek/siguiente sin salir de la
palabra. Si el archivo falta a mitad de reproducción → mensaje y fin de
pista; si el permiso se revoca → próximas peticiones responden 403/404.

## Notas

- Adaptabilidad: escritorio = biblioteca a pantalla completa con panel lateral;
  móvil = una columna, controles grandes, reproductor fijo inferior.
- Accesibilidad mínima: foco visible, roles ARIA en controles, atajo de
  teclado Espacio = play/pausa cuando el reproductor tiene foco.
- Ningún boceto muestra rutas físicas ni IDs internos al usuario final.
