from __future__ import annotations
from typing import Callable, Any
import time, ssl, socket
import logging

logger = logging.getLogger(__name__)

TRANSIENT_SNIPPETS = [
    "SSLEOFError",
    "UNEXPECTED_EOF_WHILE_READING",
    "ConnectionResetError",
    "RemoteDisconnected",
    "ReadTimeout",
    "TimeoutError",
    "ConnectionError",
]

def is_transient_exc(e: Exception) -> bool:
    msg = repr(e)
    return any(s in msg for s in TRANSIENT_SNIPPETS) or isinstance(
        e, (ssl.SSLError, TimeoutError, ConnectionError, socket.timeout, socket.gaierror)
    )

def retry_call(fn: Callable[[], Any], attempts: int = 3, base_delay: float = 0.6) -> Any:
    last_err = None
    for i in range(1, max(1, attempts) + 1):
        try:
            return fn()
        except Exception as e:
            last_err = e
            if not is_transient_exc(e) or i == attempts:
                break
            delay = base_delay * (2 ** (i - 1))
            logger.warning("[retry] Transient error (%s). Retrying in %.1fs (%d/%d)...", e.__class__.__name__, delay, i, attempts)
            time.sleep(delay)
    raise last_err  # let caller decide how to format error