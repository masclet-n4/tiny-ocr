"""Admite un solo OCR a la vez, antes de parsear el archivo recibido."""

import json
import threading


class BoundedOcrAdmission:
    def __init__(self, app):
        self.app = app
        self.slot = threading.BoundedSemaphore(1)

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"] not in ("/ocr", "/ocr/async")
        ):
            await self.app(scope, receive, send)
            return

        # Reservar antes de que FastAPI lea el multipart. El await incluye
        # también el BackgroundTask del endpoint asíncrono.
        if not self.slot.acquire(blocking=False):
            # Descartar sin almacenar: cerrar durante el upload podría hacer
            # que el cliente viera Broken pipe en vez del HTTP 429.
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                if message["type"] == "http.request" and not message.get("more_body", False):
                    break
            body = json.dumps({"detail": "OCR busy; retry later"}).encode()
            await send({
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"retry-after", b"5"),
                    (b"content-length", str(len(body)).encode()),
                ],
            })
            await send({"type": "http.response.body", "body": body})
            return

        try:
            await self.app(scope, receive, send)
        finally:
            self.slot.release()
