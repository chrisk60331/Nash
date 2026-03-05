from backboard import BackboardClient
from api.config import settings

_client: BackboardClient | None = None


def get_client() -> BackboardClient:
    global _client
    if _client is None:
        _client = BackboardClient(api_key=settings.backboard_api_key, timeout=120)
    return _client
