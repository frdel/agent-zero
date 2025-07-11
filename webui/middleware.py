from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import logging
import time

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response: Response = await call_next(request)
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; object-src 'none';"
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=()'
        response.headers['Cache-Control'] = 'no-store'
        return response

class AntiBotMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        ua = request.headers.get('user-agent', '').lower()
        if 'headless' in ua or 'python' in ua or 'curl' in ua or 'scrapy' in ua:
            return Response('Go away, bot.', status_code=403)
        return await call_next(request)

class SuspiciousActivityLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.time()
        response = await call_next(request)
        duration = time.time() - start
        if duration > 2.0 or response.status_code >= 400:
            logging.warning(f"Suspicious: {request.method} {request.url} {response.status_code} {duration:.2f}s")
        return response
