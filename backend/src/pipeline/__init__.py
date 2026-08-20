"""Phase 3 pipeline helpers."""

from .match import run_match_pipeline
from .normalize import normalize_all_source_records
from .golden import materialize_golden_customers
from .resolve import resolve_linked_customers

__all__ = [
	"materialize_golden_customers",
	"normalize_all_source_records",
	"resolve_linked_customers",
	"run_match_pipeline",
]
