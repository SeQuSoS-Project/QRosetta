from slowapi import Limiter
from slowapi.util import get_remote_address

# Global Rate Limiter Instance
# We define it here to avoid circular imports between main.py and routers
limiter = Limiter(key_func=get_remote_address)
