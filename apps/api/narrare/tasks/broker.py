"""TaskIQ broker for async background task processing (INFRA-007).

Uses Redis as both the queue transport and the result backend. The broker is
started by the application lifespan (``_app/lifespan.py``) and skipped inside
the taskiq worker process — the worker manages its own lifecycle.

All task modules are imported by ``narrare.tasks.__init__`` so that importing
this module (or the package) registers every task on the shared ``broker``
instance. The taskiq worker target is ``narrare.tasks.broker:broker``.

taskiq has no PEP 561 type stubs, hence the ``type: ignore`` below.
"""

from __future__ import annotations

from taskiq_redis import (  # type: ignore[import-untyped]
    ListQueueBroker,
    RedisAsyncResultBackend,
)

from narrare._app.config import get_settings

_settings = get_settings()

#: Shared broker instance. Importing ``narrare.tasks`` registers every
#: ``@broker.task``-decorated function on this object.
broker: ListQueueBroker = ListQueueBroker(url=_settings.redis_url)
broker.with_result_backend(RedisAsyncResultBackend(redis_url=_settings.redis_url))
