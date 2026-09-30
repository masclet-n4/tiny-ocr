"""Configuración desde variables de entorno."""

import os

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
RENDER_SCALE = float(os.getenv("OCR_RENDER_SCALE", "1.5"))
PB_URL = os.getenv("PB_URL", "http://localhost:8090")
RUSTFS_ENDPOINT = os.getenv("RUSTFS_ENDPOINT", "http://rustfs:9000")
RUSTFS_BUCKET = os.getenv("RUSTFS_BUCKET", "ocr-results")
RUSTFS_ACCESS_KEY = os.getenv("RUSTFS_ACCESS_KEY", "")
RUSTFS_SECRET_KEY = os.getenv("RUSTFS_SECRET_KEY", "")
RUSTFS_REGION = os.getenv("RUSTFS_REGION", "us-east-1")
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "tesseract")
TESSERACT_LANG = os.getenv("TESSERACT_LANG", "spa+eng")
TESSERACT_PSM = int(os.getenv("TESSERACT_PSM", "3"))

# Ajustes de memoria durante el renderizado de páginas PDF.
MEMORY_TRIM = os.getenv("OCR_MEMORY_TRIM", "1") == "1"
# Ejecutar cada documento en un proceso hijo que termina al acabar.
ISOLATE_PROCESS = os.getenv("OCR_ISOLATE_PROCESS", "1") == "1"
