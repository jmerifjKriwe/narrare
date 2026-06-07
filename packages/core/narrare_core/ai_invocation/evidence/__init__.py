"""Evidence sink implementations for the AI invocation adoption contract.

Provides structured logging, in-memory test sinks, and other
:class:`~narrare_core.ai_invocation.contracts.FeatureInvocationEvidenceSink`
implementations.

See:
    ADR-038, INFRA-013, CONSTRAINTS.md RULE-03/RULE-06.
"""

from narrare_core.ai_invocation.evidence.file_sink import FileEvidenceSink
from narrare_core.ai_invocation.evidence.logging_sink import LoggingEvidenceSink

__all__ = [
    "FileEvidenceSink",
    "LoggingEvidenceSink",
]
