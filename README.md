# tiny-ocr

API de OCR basada en Tesseract y PDFium para extraer texto de documentos PDF e imágenes. Si el PDF ya tiene capa de texto, la usa directamente; las páginas escaneadas se renderizan y procesan con Tesseract.

## Requisitos

- Docker con Docker Compose.
- PocketBase y RustFS accesibles desde el contenedor para jobs asíncronos y almacenamiento de resultados.
- Credenciales válidas de RustFS. El bucket configurado debe existir.

La imagen instala Tesseract con español e inglés. Para ejecutar Python directamente en el host, también se necesita Python 3.11, Tesseract y las dependencias de `requirements.txt`.

## Configuración

Desde este directorio, copia el ejemplo y cambia las credenciales:

```sh
cp .env.example .env
```

| Variable | Valor de ejemplo / defecto | Uso |
|---|---|---|
| `OCR_PORT` | `3000` | Puerto del host publicado por Compose; la API escucha en el 3000 del contenedor. |
| `PB_URL` | `.env.example`: `http://host.docker.internal:8090`; proceso local: `http://localhost:8090` | PocketBase donde se registra el estado de los jobs. |
| `RUSTFS_ENDPOINT` | `.env.example`: `http://host.docker.internal:9000`; proceso local: `http://rustfs:9000` | Endpoint S3 donde se guardan los resultados asíncronos. |
| `RUSTFS_BUCKET` | `ocr-results` | Bucket de los resultados. |
| `RUSTFS_ACCESS_KEY` | `.env.example`: `rustfsadmin`; proceso local: vacío | Credencial de RustFS; configura una válida. |
| `RUSTFS_SECRET_KEY` | `.env.example`: `change-me`; proceso local: vacío | Secreto de RustFS; reemplaza el valor de ejemplo. |
| `RUSTFS_REGION` | `us-east-1` | Región S3. |
| `OCR_RENDER_SCALE` | `1.5` | Escala de renderizado de páginas PDF. |
| `OCR_MEMORY_TRIM` | `1` | Intenta liberar memoria entre páginas (`1` activado). |
| `OCR_ISOLATE_PROCESS` | `1` | Procesa cada documento en un proceso hijo (`1` activado). |
| `TESSERACT_CMD` | `tesseract` | Ruta o comando del ejecutable Tesseract. |
| `TESSERACT_LANG` | `spa+eng` | Idiomas de Tesseract; la imagen incluye español e inglés. |
| `TESSERACT_PSM` | `3` | Modo de segmentación de página de Tesseract. |

`PB_URL` y `RUSTFS_ENDPOINT` deben apuntar a servicios accesibles desde el contenedor. Si ejecutas la API directamente en el host, normalmente usarás `localhost`.

## Ejecución

Desde este directorio:

```sh
docker compose up --build -d
docker compose ps
```

- API: <http://localhost:3000>
- Healthcheck: <http://localhost:3000/alive>

Para ver logs y detener el contenedor:

```sh
docker compose logs -f ocr
docker compose down
```

## API

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/alive` | Healthcheck. |
| `POST` | `/ocr` | OCR síncrono de un PDF o imagen; devuelve texto plano. |
| `POST` | `/ocr/async` | Inicia un job y devuelve `{ "job_id": ... }`. |
| `GET` | `/jobs/{job_id}` | Devuelve estado y, al terminar, la clave del resultado en RustFS. |

Se admiten archivos de hasta 10 MB. Cada proceso acepta un único OCR a la vez; las solicitudes concurrentes reciben HTTP 429 con `Retry-After: 5`. No hay cola interna. En la ruta asíncrona la plaza queda ocupada hasta que termina el job. La limitación es por proceso, así que cada worker o réplica puede aceptar una solicitud simultánea.

Los resultados asíncronos se guardan en RustFS bajo el bucket configurado. La API devuelve `result_key`, no sirve directamente el archivo; otro backend puede generar una URL firmada para descargarlo.

## Pruebas

Con las dependencias instaladas:

```sh
python -m unittest discover -s app
```

## Notas de despliegue

PocketBase y RustFS corren fuera del Compose de este servicio. En Linux se configura `host.docker.internal` hacia el host; asegúrate de que ambos servicios acepten conexiones desde Docker y limita el acceso con el firewall.

PocketBase debe tener la colección `jobs` configurada. Sus reglas de escritura deben protegerse antes de exponer PocketBase a Internet.
