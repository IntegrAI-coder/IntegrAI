# IntegrAI · Frontend del dashboard

Interfaz de solo consulta para revisar las clasificaciones de nivel de desarrollo
(1–9) de niños y niñas a partir de las observaciones de las educadoras. No edita
datos ni accede a ningún backend.

**Demo en vivo:** https://integrai-coder.github.io/IntegrAI/ (GitHub Pages) · https://d2eg8hbkfurj9b.cloudfront.net (CloudFront, la web oficial del proyecto)

## Requisitos

- Node.js 18+ y npm.

## Cómo correrlo

```bash
cd frontend
npm i
npm run dev     # servidor de desarrollo (Vite)
npm test        # tests de dominio (Vitest)
npm run build   # chequeo de tipos + build de producción
```

Abre la URL que imprime Vite (por defecto http://localhost:5173).

## Datos

Los CSV viven en `../data` (raíz del repo) y **no se copian** a este proyecto.
`vite.config.ts` usa `publicDir: '../data'`, así que Vite los sirve (en dev) y los
incluye en `dist/` (en build). Las rutas se arman con `import.meta.env.BASE_URL`
(`src/data/cargar.ts`), para que funcionen tanto en local (`/ninos.csv`) como bajo
el subpath de GitHub Pages (`/IntegrAI/ninos.csv`).

Cada CSV se carga **una sola vez** al iniciar la app en `DatosProvider`
(`src/data/DatosContext.tsx`) y se comparte entre las tres vistas mediante React
Context. Así ~2.950 observaciones y ~500 niños se parsean una vez y no en cada
navegación.

## Despliegue (GitHub Pages)

El sitio se publica automáticamente en
https://integrai-coder.github.io/IntegrAI/ mediante
`.github/workflows/pages.yml`: en cada push a `main` que toque `frontend/**` o
`data/**`, la CI corre `npm ci && npm test && npm run build` dentro de `frontend/`
y publica `frontend/dist` con `actions/deploy-pages` (Node 20).

Como Pages sirve bajo el subpath `/IntegrAI/`, el proyecto usa
`base: '/IntegrAI/'` en `vite.config.ts` y `HashRouter` (las rutas quedan como
`/IntegrAI/#/curso/...`), de modo que recargar una vista profunda no da 404.

## Despliegue (CloudFront, web oficial)

La raíz de https://d2eg8hbkfurj9b.cloudfront.net sirve este mismo frontend desde un bucket S3 **privado** (solo CloudFront lo lee vía OAC). Como allí la app vive en `/` y no en `/IntegrAI/`, el build se hace con `--base=/`:

```bash
python tools/desplegar_frontend.py subir   # npm ci && npm run build -- --base=/  → S3 → invalidación
```

Solo se publican `index.html`, `assets/` y los 6 CSV que lee `src/data/cargar.ts`. Los dos despliegues (Pages y CloudFront) salen del mismo código de `main`.

## Estructura

```
src/
  domain/      Tipos, métricas puras y consultas derivadas (+ tests Vitest)
  data/        Carga y parseo de CSV (PapaParse) y Context de datos
  pages/       Cursos, Curso, Nino
  components/  Tabla ordenable, badges, breadcrumbs, gráficos, estados
```

### Lógica de dominio (`src/domain/`)

Todos los cálculos son funciones puras, probadas con Vitest:

- `edadMeses(fechaNac, hoy)` — edad en meses completos (nunca negativa).
- `nivelEsperado(meses, niveles)` — nivel según los rangos de `ruta_niveles.csv`.
- `brecha = nivelVigente − nivelEsperado`.
- `tieneAlerta` cuando `brecha <= UMBRAL_ALERTA` (`-2`, constante en `metrics.ts`).
- `consultas.ts` arma los modelos de vista (resumen de cursos, alumnos, ficha).

**Curso** = `id_jardin + sala_grupo`. **Nivel vigente** = `nivel_estimado` de la
observación más reciente del niño/a.

## Vistas

1. `/` — Lista de cursos (jardín, comuna, sala, n.º de niños/as, nivel promedio,
   n.º de alertas) con buscador de texto.
2. `/curso/:idJardin/:sala` — Resumen del curso, gráfico de barras de la
   distribución por nivel (1–9) y tabla de alumnos con columnas ordenables.
3. `/nino/:idNino` — Nivel vigente con nombre y descripción, brecha, gráfico de
   línea con la trayectoria y lista de observaciones con sus manifestaciones.

Navegación con breadcrumbs: Cursos › Curso › Niño/a.

## Privacidad

Solo se muestran códigos (`NINO-00001`), nunca nombres ni RUT. El dato
`sexo_registrado` del CSV no se muestra. Pie de página fijo: «Herramienta de
apoyo pedagógico, no constituye diagnóstico clínico».

## Decisiones tomadas donde el spec no era explícito

- **Rangos de nivel**: `edad_min_meses` inclusivo y `edad_max_meses` exclusivo.
  Si la edad supera el rango del nivel 9 (36 meses) se asigna el nivel 9; si no
  cae en ningún rango, `nivelEsperado` es `null` y la brecha/alerta quedan en
  blanco (`—`) en vez de inventar un valor.
- **Nivel promedio del curso**: promedio de los niveles vigentes disponibles;
  los niños/as sin observaciones no cuentan. Se muestra con un decimal.
- **Fecha "hoy"**: se usa la fecha del navegador (`new Date()`) para la edad.
- **Orden de observaciones**: la ficha las lista de la más reciente a la más
  antigua; el gráfico de trayectoria va de la más antigua a la más reciente.
- **Ruta desconocida**: cualquier URL no reconocida redirige a `/`.
- **Estilos**: CSS plano con variables, tipografía del sistema, acento azul y
  ámbar para alertas. Responsive desde 360 px, foco visible y HTML semántico.

## Fuera de alcance

Autenticación, edición de niveles, backend, despliegue, modo oscuro e
internacionalización.
