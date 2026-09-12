"""
ContractIQ — Evaluation Dataset Loader & Models (Phase 5D)

Provides strongly typed schemas for retrieval benchmarks and a loader
for the version-controlled benchmark dataset in JSON format.
"""

import json
from pathlib import Path
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


DEFAULT_DATASET_PATH = Path(__file__).parent / "data" / "retrieval_eval_dataset.json"


class EvalChunk(BaseModel):
    """A contract document chunk for evaluation."""

    id: uuid.UUID = Field(..., description="Unique chunk UUID")
    chunk_index: int = Field(..., ge=0, description="0-indexed chunk sequence order")
    page_number: int = Field(..., ge=1, description="1-indexed source PDF page number")
    section_header: Optional[str] = Field(default=None, description="Section heading")
    text: str = Field(..., min_length=1, description="Verbatim chunk text")
    char_start: Optional[int] = Field(default=None, ge=0)
    char_end: Optional[int] = Field(default=None, ge=0)
    vector_axis: int = Field(
        default=0,
        ge=0,
        le=767,
        description="Deterministic orthogonal axis index for mock embeddings",
    )

    model_config = ConfigDict(from_attributes=True)


class EvalContract(BaseModel):
    """The contract representation in the evaluation dataset."""

    id: uuid.UUID = Field(..., description="Unique contract UUID")
    title: str = Field(..., min_length=1)
    vendor: str = Field(..., min_length=1)
    contract_type: str = Field(default="MSA")
    status: str = Field(default="active")
    chunks: list[EvalChunk] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class EvalQuery(BaseModel):
    """A test query with ground-truth relevant chunk IDs."""

    query_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    query_type: str = Field(default="hybrid", description="semantic | keyword | hybrid")
    vector_axis: int = Field(
        default=0,
        ge=0,
        le=767,
        description="Deterministic orthogonal axis index for mock query vector",
    )
    expected_chunk_ids: list[uuid.UUID] = Field(
        default_factory=list,
        min_length=1,
        description="Ground-truth relevant chunk UUIDs",
    )
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RetrievalEvalDataset(BaseModel):
    """Complete retrieval evaluation benchmark dataset."""

    version: str = Field(default="1.0")
    name: str = Field(..., min_length=1)
    description: str = Field(default="")
    contract: EvalContract
    queries: list[EvalQuery] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


def load_default_eval_dataset(path: Optional[Path | str] = None) -> RetrievalEvalDataset:
    """
    Loads and validates the evaluation dataset from disk.

    Args:
        path: Optional custom file path; defaults to data/retrieval_eval_dataset.json.

    Returns:
        RetrievalEvalDataset: Validated dataset instance.

    Raises:
        FileNotFoundError: If dataset file does not exist.
        ValueError: If JSON data fails validation.
    """
    target_path = Path(path) if path else DEFAULT_DATASET_PATH
    if not target_path.is_file():
        raise FileNotFoundError(f"Evaluation dataset file not found at: {target_path}")

    with open(target_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return RetrievalEvalDataset.model_validate(data)
