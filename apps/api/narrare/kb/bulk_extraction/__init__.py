"""KB bulk extraction sub-package (F2, ADR-092).

Contracts-first sub-package for the server-side bulk extraction job:
contracts + wire schemas land first (T1); the in-memory registry, shared
budget pacer, asyncio runner, service, and router follow (T2-T6), mirroring
the ``kb/entity_resolution`` package precedent. Dependency direction is
one-way (RULE-07): router → service → registry/runner/pacer →
ExtractionService → repos → DB.
"""
