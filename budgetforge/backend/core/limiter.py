from slowapi import Limiter
from slowapi.util import get_remote_address

# Rate limiting robuste pour production
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],  # Limite par défaut plus généreuse
)
