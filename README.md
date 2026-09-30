# tiny-ocr

Servicio OCR ligero basado en **Tesseract** y PDFium para transcribir documentos PDF e imágenes.

## Cómo funciona

1. **Capa de texto primero**: si el PDF tiene texto embebido, se extrae directamente (instantáneo, 100% preciso).
2. **Fallback OCR**: las páginas sin capa de texto se renderizan con PDFium y se procesan con Tesseract.

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/alive` | Healthcheck |
| POST | `/ocr` | OCR síncrono (PDF o imagen) → texto plano |
| POST | `/ocr/async` | OCR asíncrono → `{job_id}` |
| GET | `/jobs/{job_id}` | Estado del job y referencia al resultado en RustFS |

**Límite**: archivos de hasta 10 MB (HTTP 413 si se supera).

Solo se admite **una solicitud OCR a la vez por proceso**, compartida por
`POST /ocr` y `POST /ocr/async`. Mientras se procesa un archivo, las nuevas
solicitudes reciben HTTP `429` con `Retry-After: 5`; el servicio no almacena
una cola de PDFs. Quien llama al OCR puede gestionar su propia cola y reintentar
tras ese intervalo. En la ruta asíncrona la plaza permanece ocupada hasta que
el job termina, no solo hasta recibir su `job_id`. `GET /alive` y
`GET /jobs/{job_id}` siguen disponibles durante el procesamiento.

El límite es por proceso Uvicorn: si se configuran varios workers o réplicas,
cada uno podría admitir una solicitud simultáneamente.

## Memoria

El procesamiento OCR y de PDF puede aislarse por documento y configurarse en `.env`:

| Variable | Defecto | Efecto |
|---|---|---|
| `OCR_ISOLATE_PROCESS` | `1` | Cada documento se procesa en un proceso hijo desechable. Si el worker muere, el job pasa a `error` y la API sigue funcionando. |
| `OCR_MEMORY_TRIM` | `1` | `gc.collect()` + `malloc_trim(0)` tras cada página OCR; baja el pico y la memoria retenida. |
| `TESSERACT_LANG` | `spa+eng` | Idiomas Tesseract a usar; el contenedor incluye español e inglés. |
| `TESSERACT_PSM` | `3` | Modo de segmentación de página de Tesseract. |

Los PDFs subidos se copian a disco por bloques, sin cargarlos enteros en
memoria. El uso real depende del tamaño y la resolución de las páginas; mídelo
en la VPS antes de fijar un límite de memoria.

Los resultados de los jobs asíncronos se guardan siempre en RustFS, dentro del
bucket configurado en `RUSTFS_BUCKET`. La respuesta de un job terminado incluye
`result_key`, que identifica el fichero dentro del bucket. La API OCR no sirve
ni descarga el fichero; otro backend puede generar una URL presignada para que
el navegador lo descargue directamente desde RustFS.

## Docker Compose

Compose levanta únicamente la API OCR. PocketBase y RustFS deben estar
ejecutándose en el host; configura sus URLs en `.env`. En Linux, Compose crea
`host.docker.internal` apuntando al host. Asegúrate de que PocketBase y RustFS
acepten conexiones desde la interfaz de Docker (no solo desde `127.0.0.1`) y
limita el acceso con el firewall.

```bash
cp .env.example .env
# Ajusta RUSTFS_ACCESS_KEY y RUSTFS_SECRET_KEY a las credenciales locales
docker compose up --build -d
docker compose ps
```

- API OCR: <http://localhost:3000>
- Estado de la API: <http://localhost:3000/alive>

Los puertos por defecto de PocketBase y RustFS son `8090` y `9000`; si usas
otros, cambia `PB_URL` y `RUSTFS_ENDPOINT` en `.env`. Esas direcciones se
interpretan desde el contenedor OCR. Para ejecutar la API directamente en el
host, usa `localhost` en ambas URLs.

La migración de `pocketbase/pb_migrations` crea la colección `jobs` al arrancar
PocketBase por primera vez. Sus reglas actuales permiten crear/actualizar jobs
públicamente para compatibilidad; no expongas PocketBase a Internet sin añadir
autenticación entre la API OCR y PocketBase.

Los datos y resultados permanecen bajo la gestión de PocketBase y RustFS;
`docker compose down` solo detiene la API OCR. Para ver sus logs:

```bash
docker compose logs -f ocr
```

La escala de renderizado, los idiomas y el puerto OCR se configuran con
`OCR_RENDER_SCALE`, `TESSERACT_LANG`, `TESSERACT_PSM` y `OCR_PORT`.
