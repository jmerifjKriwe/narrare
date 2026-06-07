"""Evidence module — persistent evidence store for AI invocations.

Provides the SQLAlchemy ORM model, repository, and persistent sink
for ``FeatureInvocationEvidence`` records (ADR-042).

Privacy guarantee (ADR-038): The schema contains zero prompt text,
zero user prose, and zero eval case content.
"""

from narrare.evidence.models import InvocationEvidenceModel
from narrare.evidence.sink import PersistentEvidenceSink

__all__ = [
    "InvocationEvidenceModel",
    "PersistentEvidenceSink",
]
