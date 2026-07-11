"""Whinfell data pipeline — adapter layer, canonical schema, Parquet normalization."""

from whinfell_pipeline.canonical import DecisionBundle, ValidationStatus

__all__ = [
    "DecisionBundle",
    "ValidationStatus",
    "ingest_payload",
    "ingest_file",
]


def ingest_payload(*args, **kwargs):
    from whinfell_pipeline.ingest import ingest_payload as _ingest_payload

    return _ingest_payload(*args, **kwargs)


def ingest_file(*args, **kwargs):
    from whinfell_pipeline.ingest import ingest_file as _ingest_file

    return _ingest_file(*args, **kwargs)