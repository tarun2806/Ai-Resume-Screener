import os

from slowapi import Limiter
from slowapi.util import get_remote_address

# Disabled in tests (RATE_LIMIT_ENABLED=false) since TestClient shares one bucket.
limiter = Limiter(
    key_func=get_remote_address,
    enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() != "false",
)
