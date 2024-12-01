import requests
import requests.adapters


class SSLContextAdapter(requests.adapters.HTTPAdapter):
    # HTTPAdapter for Requests that allows for injecting an SSLContext
    # into the lower-level urllib3.PoolManager.
    def __init__(self, *, ssl_context=None, **kwargs):
        self._ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        if self._ssl_context is not None:
            kwargs.setdefault("ssl_context", self._ssl_context)
        return super().init_poolmanager(*args, **kwargs)
