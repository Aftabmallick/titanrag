import gzip
import io
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

try:
    import brotli

    HAS_BROTLI = True
except ImportError:
    HAS_BROTLI = False


class CompressionMiddleware(BaseHTTPMiddleware):
    """Production Response Compression Middleware.

    Compresses HTTP responses using Brotli (preferred) or Gzip.
    Intelligently bypasses:
    - Server-Sent Events (SSE) `text/event-stream` streaming endpoints
    - WebSocket upgrade requests
    - Small payloads (< 1024 bytes)
    - Already compressed binary assets (images, zip, pdf)
    """

    EXCLUDED_CONTENT_TYPES = {
        "text/event-stream",
        "application/zip",
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/webp",
        "audio/mpeg",
        "video/mp4",
    }

    def __init__(self, app: ASGIApp, minimum_size: int = 1024):
        super().__init__(app)
        self.minimum_size = minimum_size

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response: Response = await call_next(request)

        # Check content-type bypass
        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        if content_type in self.EXCLUDED_CONTENT_TYPES:
            return response

        # Check accept-encoding
        accept_encoding = request.headers.get("accept-encoding", "").lower()
        if not accept_encoding:
            return response

        # Check body availability (streaming responses without direct body are preserved)
        if not hasattr(response, "body") or len(response.body) < self.minimum_size:
            return response

        body = response.body

        # 1. Try Brotli
        if HAS_BROTLI and "br" in accept_encoding:
            compressed = brotli.compress(body, quality=4)
            response.headers["content-encoding"] = "br"
            response.headers["content-length"] = str(len(compressed))
            response.headers["vary"] = "Accept-Encoding"
            return Response(
                content=compressed,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        # 2. Try Gzip
        if "gzip" in accept_encoding:
            gzip_buffer = io.BytesIO()
            with gzip.GzipFile(mode="wb", fileobj=gzip_buffer, compresslevel=6) as gz:
                gz.write(body)
            compressed = gzip_buffer.getvalue()

            response.headers["content-encoding"] = "gzip"
            response.headers["content-length"] = str(len(compressed))
            response.headers["vary"] = "Accept-Encoding"
            return Response(
                content=compressed,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        return response
