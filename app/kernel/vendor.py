"""Where a vendor endpoint lives, and whether it needs a key.

Both strategy families (text and embeddings) talk to an OpenAI-shaped endpoint,
so both need the same two facts. A server on this machine answers without
credentials; anything else needs one, or the first request comes back 401 far
from the configuration mistake that caused it.
"""

import httpx

LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1", "host.docker.internal")


def needs_api_key(base_url: str) -> bool:
    """True when the endpoint is not on this machine."""
    return httpx.URL(base_url).host not in LOCAL_HOSTS
