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


# ====================================================================
# Grounded RAG Evaluation Models & Schemas (Phase 17B, 17C, 17D)
# ====================================================================

DEFAULT_GROUNDED_DATASET_PATH = Path(__file__).parent / "data" / "grounded_eval_dataset.json"


class GroundedEvalCitation(BaseModel):
    """Citation specification for grounded evaluation test cases."""

    contract_id: Optional[uuid.UUID] = None
    chunk_id: Optional[str] = None
    page_number: Optional[int] = None
    verbatim_quote: str = ""
    expected_status: str = Field(
        default="VALID",
        description="Expected status: VALID, WRONG_CONTRACT, CHUNK_NOT_FOUND, TEXT_MISMATCH, PAGE_MISMATCH",
    )

    model_config = ConfigDict(from_attributes=True)


class GroundedEvalClaim(BaseModel):
    """Factual claim in an evaluation response with supporting citations."""

    claim_text: str = Field(..., min_length=1)
    citations: list[GroundedEvalCitation] = Field(default_factory=list)
    is_grounded: bool = True

    model_config = ConfigDict(from_attributes=True)


class GroundedEvalCase(BaseModel):
    """A test scenario for evaluating grounded RAG quality, citations, or failure modes."""

    case_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    scope: str = Field(default="single", description="'single' or 'cross'")
    contract_ids: list[uuid.UUID] = Field(default_factory=list)
    expected_status: str = Field(
        default="answered",
        description="answered | insufficient_evidence | no_retrieval_matches | low_retrieval_confidence",
    )
    expected_has_sufficient_evidence: bool = True
    failure_mode: Optional[str] = Field(
        default=None,
        description="Failure mode key if testing a specific failure condition",
    )
    mock_answer: Optional[str] = None
    mock_claims: list[GroundedEvalClaim] = Field(default_factory=list)
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class GroundedEvaluationDataset(BaseModel):
    """Complete grounded RAG evaluation suite dataset."""

    version: str = Field(default="1.0")
    name: str = Field(..., min_length=1)
    description: str = Field(default="")
    contracts: list[EvalContract] = Field(default_factory=list)
    cases: list[GroundedEvalCase] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


def load_grounded_eval_dataset(path: Optional[Path | str] = None) -> GroundedEvaluationDataset:
    """
    Loads and validates the grounded RAG evaluation dataset from disk.
    If the specified/default JSON file does not exist, falls back to the
    in-code reference benchmark dataset.
    """
    target_path = Path(path) if path else DEFAULT_GROUNDED_DATASET_PATH
    if target_path.is_file():
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return GroundedEvaluationDataset.model_validate(data)

    return get_default_grounded_eval_dataset()


def get_default_grounded_eval_dataset() -> GroundedEvaluationDataset:
    """
    Returns the comprehensive built-in reference grounded evaluation dataset
    covering single-contract queries, cross-contract comparisons, and all
    13 core failure modes.
    """
    c1_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    c2_id = uuid.UUID("22222222-2222-4222-8222-222222222222")
    c3_id = uuid.UUID("33333333-3333-4333-8333-333333333333")

    ch1_id = uuid.UUID("aaaa0001-0001-4001-8001-000000000001")
    ch2_id = uuid.UUID("aaaa0002-0002-4002-8002-000000000002")
    ch3_id = uuid.UUID("aaaa0003-0003-4003-8003-000000000003")
    ch4_id = uuid.UUID("aaaa0004-0004-4004-8004-000000000004")
    ch5_id = uuid.UUID("aaaa0005-0005-4005-8005-000000000005")

    ch6_id = uuid.UUID("bbbb0001-0001-4001-8001-000000000001")
    ch7_id = uuid.UUID("bbbb0002-0002-4002-8002-000000000002")

    contracts = [
        EvalContract(
            id=c1_id,
            title="Enterprise Cloud Services Master Agreement",
            vendor="NovaScale Cloud Solutions LLC",
            contract_type="MSA",
            status="active",
            chunks=[
                EvalChunk(
                    id=ch1_id,
                    chunk_index=0,
                    page_number=1,
                    section_header="Section 1. Termination and Notice Period",
                    text="Either party may terminate this Agreement for convenience upon sixty (60) days prior written notice to the other party. In the event of a material breach, the non-breaching party may terminate immediately if such breach remains uncured thirty (30) days following receipt of written notification.",
                    char_start=0,
                    char_end=286,
                    vector_axis=0,
                ),
                EvalChunk(
                    id=ch2_id,
                    chunk_index=1,
                    page_number=1,
                    section_header="Section 2. Limitation of Liability",
                    text="Except for indemnification obligations under Section 3, each party's maximum aggregate liability arising out of or related to this Agreement shall be strictly capped at the total fees paid by customer in the twelve (12) months preceding the incident giving rise to liability.",
                    char_start=287,
                    char_end=561,
                    vector_axis=1,
                ),
                EvalChunk(
                    id=ch3_id,
                    chunk_index=2,
                    page_number=2,
                    section_header="Section 3. Indemnification and IP Defense",
                    text="Vendor agrees to defend, indemnify, and hold harmless Customer and its officers from and against any third-party claims, liabilities, losses, and damages alleging that the Cloud Services infringe any valid patent, copyright, or misappropriates any trade secret of a third party.",
                    char_start=0,
                    char_end=279,
                    vector_axis=2,
                ),
                EvalChunk(
                    id=ch4_id,
                    chunk_index=3,
                    page_number=2,
                    section_header="Section 4. Confidentiality and Non-Disclosure",
                    text="Recipient shall hold Discloser's Proprietary and Confidential Information in strict trust, using at least reasonable care. Neither party shall disclose trade secrets or proprietary technical data without prior written consent, except to authorized employees bound by equivalent non-disclosure duties.",
                    char_start=280,
                    char_end=580,
                    vector_axis=3,
                ),
                EvalChunk(
                    id=ch5_id,
                    chunk_index=4,
                    page_number=3,
                    section_header="Section 5. Governing Law and Dispute Resolution",
                    text="This Agreement shall be governed exclusively by the laws of the State of Delaware, without regard to conflicts of law provisions. The state and federal courts situated in Wilmington, Delaware shall possess exclusive jurisdiction to adjudicate any dispute arising under this Agreement.",
                    char_start=0,
                    char_end=285,
                    vector_axis=4,
                ),
            ],
        ),
        EvalContract(
            id=c2_id,
            title="Apex Analytics Vendor SaaS Agreement",
            vendor="Apex Data Systems Inc",
            contract_type="SaaS",
            status="active",
            chunks=[
                EvalChunk(
                    id=ch6_id,
                    chunk_index=0,
                    page_number=1,
                    section_header="Section 1. Term and Renewal",
                    text="This Agreement commences on the Effective Date and continues for an initial term of two (2) years. Thereafter, it shall automatically renew for successive one (1) year periods unless either party gives written notice of non-renewal at least ninety (90) days prior to the expiration of the then-current term.",
                    char_start=0,
                    char_end=312,
                    vector_axis=5,
                ),
                EvalChunk(
                    id=ch7_id,
                    chunk_index=1,
                    page_number=1,
                    section_header="Section 2. Liability and Fees",
                    text="Under no circumstances shall either party's aggregate liability exceed the fixed sum of $500,000. Invoices are payable net 30 days from date of issue. Late payments incur a fee of 1.5% per month.",
                    char_start=313,
                    char_end=510,
                    vector_axis=6,
                ),
            ],
        ),
        EvalContract(
            id=c3_id,
            title="Empty Logistics Archive Agreement",
            vendor="OmniCorp Logistics LLC",
            contract_type="Facility",
            status="draft",
            chunks=[],
        ),
    ]

    cases = [
        # 17B: Clearly supported claims
        GroundedEvalCase(
            case_id="case-01-supported-termination",
            title="Termination Notice Grounded Answer",
            query="What is the notice period required to terminate the agreement for convenience?",
            scope="single",
            contract_ids=[c1_id],
            expected_status="answered",
            expected_has_sufficient_evidence=True,
            mock_answer="The agreement may be terminated for convenience upon 60 days prior written notice.",
            mock_claims=[
                GroundedEvalClaim(
                    claim_text="Either party may terminate for convenience upon sixty (60) days prior written notice.",
                    citations=[
                        GroundedEvalCitation(
                            contract_id=c1_id,
                            chunk_id=str(ch1_id),
                            page_number=1,
                            verbatim_quote="Either party may terminate this Agreement for convenience upon sixty (60) days prior written notice to the other party.",
                            expected_status="VALID",
                        )
                    ],
                    is_grounded=True,
                )
            ],
        ),
        # 17B: Supported claim with multiple citations
        GroundedEvalCase(
            case_id="case-02-supported-liability",
            title="Liability Cap Grounded Answer",
            query="What is the liability cap under the agreement?",
            scope="single",
            contract_ids=[c1_id],
            expected_status="answered",
            expected_has_sufficient_evidence=True,
            mock_answer="Liability is capped at the total fees paid by customer in the preceding 12 months.",
            mock_claims=[
                GroundedEvalClaim(
                    claim_text="Aggregate liability is capped at the total fees paid in the preceding twelve months.",
                    citations=[
                        GroundedEvalCitation(
                            contract_id=c1_id,
                            chunk_id=str(ch2_id),
                            page_number=1,
                            verbatim_quote="each party's maximum aggregate liability arising out of or related to this Agreement shall be strictly capped at the total fees paid by customer in the twelve (12) months preceding the incident giving rise to liability.",
                            expected_status="VALID",
                        )
                    ],
                    is_grounded=True,
                )
            ],
        ),
        # 17B: Multi-contract comparative question
        GroundedEvalCase(
            case_id="case-03-cross-contract-comparison",
            title="Cross-Contract Liability Comparison",
            query="Compare the liability limits between NovaScale and Apex agreements.",
            scope="cross",
            contract_ids=[c1_id, c2_id],
            expected_status="answered",
            expected_has_sufficient_evidence=True,
            mock_answer="NovaScale limits liability to 12 months fees paid, while Apex caps liability at $500,000.",
            mock_claims=[
                GroundedEvalClaim(
                    claim_text="NovaScale liability is capped at total fees paid in the preceding 12 months.",
                    citations=[
                        GroundedEvalCitation(
                            contract_id=c1_id,
                            chunk_id=str(ch2_id),
                            page_number=1,
                            verbatim_quote="strictly capped at the total fees paid by customer in the twelve (12) months preceding the incident",
                            expected_status="VALID",
                        )
                    ],
                    is_grounded=True,
                ),
                GroundedEvalClaim(
                    claim_text="Apex liability is capped at the fixed amount of $500,000.",
                    citations=[
                        GroundedEvalCitation(
                            contract_id=c2_id,
                            chunk_id=str(ch7_id),
                            page_number=1,
                            verbatim_quote="Under no circumstances shall either party's aggregate liability exceed the fixed sum of $500,000.",
                            expected_status="VALID",
                        )
                    ],
                    is_grounded=True,
                ),
            ],
        ),
        # 17C & 17D (Failure Mode 1): No retrieval matches found
        GroundedEvalCase(
            case_id="case-04-no-retrieval-matches",
            title="No Retrieval Matches Found",
            query="What are the specific requirements for cryogenic refrigeration facilities?",
            scope="single",
            contract_ids=[c3_id],
            expected_status="no_retrieval_matches",
            expected_has_sufficient_evidence=False,
            failure_mode="no_retrieval_matches",
            description="Query targets a contract with no document chunks.",
        ),
        # 17C & 17D (Failure Mode 2): Insufficient evidence in retrieved chunks
        GroundedEvalCase(
            case_id="case-05-insufficient-evidence",
            title="Insufficient Evidence in Context",
            query="What is the discount rate if payment is made within 10 days?",
            scope="single",
            contract_ids=[c1_id],
            expected_status="insufficient_evidence",
            expected_has_sufficient_evidence=False,
            failure_mode="insufficient_evidence",
            mock_answer="The contract does not specify any early payment discount terms.",
            description="Query asks for a specific contractual term that is not stated anywhere.",
        ),
        # 17C & 17D (Failure Mode 3): Low retrieval confidence
        GroundedEvalCase(
            case_id="case-06-low-retrieval-confidence",
            title="Low Retrieval Confidence Scoring",
            query="quantum encryption standards",
            scope="single",
            contract_ids=[c1_id],
            expected_status="low_retrieval_confidence",
            expected_has_sufficient_evidence=False,
            failure_mode="low_retrieval_confidence",
            description="Top match score falls below the required threshold.",
        ),
        # 17C & 17D (Failure Mode 4): Non-existent chunk ID
        GroundedEvalCase(
            case_id="case-07-non-existent-chunk",
            title="Citation with Non-Existent Chunk ID",
            query="What is the notice period for convenience?",
            scope="single",
            contract_ids=[c1_id],
            expected_status="answered",
            expected_has_sufficient_evidence=True,
            failure_mode="chunk_not_found",
            mock_claims=[
                GroundedEvalClaim(
                    claim_text="The contract requires 60 days notice.",
                    citations=[
                        GroundedEvalCitation(
                            contract_id=c1_id,
                            chunk_id="99999999-9999-9999-9999-999999999999",
                            page_number=1,
                            verbatim_quote="Either party may terminate this Agreement for convenience upon sixty (60) days prior written notice",
                            expected_status="CHUNK_NOT_FOUND",
                        )
                    ],
                    is_grounded=False,
                )
            ],
            description="LLM cites an invented chunk ID that does not exist in the database.",
        ),
        # 17C & 17D (Failure Mode 5): Wrong contract ID
        GroundedEvalCase(
            case_id="case-08-wrong-contract-citation",
            title="Citation to Wrong Contract ID",
            query="What is the initial term length of the NovaScale agreement?",
            scope="single",
            contract_ids=[c1_id],
            expected_status="answered",
            expected_has_sufficient_evidence=True,
            failure_mode="wrong_contract",
            mock_claims=[
                GroundedEvalClaim(
                    claim_text="The agreement continues for an initial term of two years.",
                    citations=[
                        GroundedEvalCitation(
                            contract_id=c1_id,
                            chunk_id=str(ch6_id),  # Belongs to c2_id, not c1_id
                            page_number=1,
                            verbatim_quote="initial term of two (2) years",
                            expected_status="WRONG_CONTRACT",
                        )
                    ],
                    is_grounded=False,
                )
            ],
            description="Citation points to a chunk from a different contract.",
        ),
        # 17C & 17D (Failure Mode 6): Text mismatch / hallucinated quote
        GroundedEvalCase(
            case_id="case-09-text-mismatch",
            title="Citation with Hallucinated Quote Snippet",
            query="What is the notice period for termination?",
            scope="single",
            contract_ids=[c1_id],
            expected_status="answered",
            expected_has_sufficient_evidence=True,
            failure_mode="text_mismatch",
            mock_claims=[
                GroundedEvalClaim(
                    claim_text="The agreement requires thirty days notice.",
                    citations=[
                        GroundedEvalCitation(
                            contract_id=c1_id,
                            chunk_id=str(ch1_id),
                            page_number=1,
                            verbatim_quote="party may terminate for convenience upon ninety (90) days notice",
                            expected_status="TEXT_MISMATCH",
                        )
                    ],
                    is_grounded=False,
                )
            ],
            description="Verbatim quote was fabricated or altered by the LLM.",
        ),
        # 17C & 17D (Failure Mode 7): Page mismatch
        GroundedEvalCase(
            case_id="case-10-page-mismatch",
            title="Citation with Incorrect Page Number",
            query="What is the governing law?",
            scope="single",
            contract_ids=[c1_id],
            expected_status="answered",
            expected_has_sufficient_evidence=True,
            failure_mode="page_mismatch",
            mock_claims=[
                GroundedEvalClaim(
                    claim_text="Delaware law governs the agreement.",
                    citations=[
                        GroundedEvalCitation(
                            contract_id=c1_id,
                            chunk_id=str(ch5_id),
                            page_number=99,  # Chunk is on page 3
                            verbatim_quote="laws of the State of Delaware",
                            expected_status="PAGE_MISMATCH",
                        )
                    ],
                    is_grounded=False,
                )
            ],
            description="Citation references page 99 when the chunk is on page 3.",
        ),
        # 17C & 17D (Failure Mode 8): Malformed LLM output
        GroundedEvalCase(
            case_id="case-11-malformed-llm-output",
            title="Malformed LLM Output Schema",
            query="What are the confidentiality obligations?",
            scope="single",
            contract_ids=[c1_id],
            expected_status="handled_failure",
            expected_has_sufficient_evidence=False,
            failure_mode="malformed_llm_output",
            description="LLM returns corrupted JSON or missing required fields.",
        ),
        # 17C & 17D (Failure Mode 9): LLM provider failure/timeout
        GroundedEvalCase(
            case_id="case-12-llm-provider-failure",
            title="LLM Provider Network Failure / Timeout",
            query="Summarize indemnification.",
            scope="single",
            contract_ids=[c1_id],
            expected_status="handled_failure",
            expected_has_sufficient_evidence=False,
            failure_mode="llm_provider_failure",
            description="Provider raises network timeout or 503 Service Unavailable.",
        ),
        # 17C & 17D (Failure Mode 10): Empty / malformed context input
        GroundedEvalCase(
            case_id="case-13-empty-context",
            title="Empty or Malformed Context Input",
            query="What is the payment term?",
            scope="single",
            contract_ids=[c1_id],
            expected_status="insufficient_evidence",
            expected_has_sufficient_evidence=False,
            failure_mode="empty_context",
            description="Context builder receives no matches or empty chunks.",
        ),
        # 17C & 17D (Failure Mode 11): Conflicting facts across chunks
        GroundedEvalCase(
            case_id="case-14-conflicting-facts",
            title="Conflicting Facts Handled with Grounded Citations",
            query="What are the different liability caps across sections?",
            scope="single",
            contract_ids=[c1_id],
            expected_status="answered",
            expected_has_sufficient_evidence=True,
            failure_mode="conflicting_facts",
            mock_claims=[
                GroundedEvalClaim(
                    claim_text="General liability is capped at 12 months fees under Section 2.",
                    citations=[
                        GroundedEvalCitation(
                            contract_id=c1_id,
                            chunk_id=str(ch2_id),
                            page_number=1,
                            verbatim_quote="maximum aggregate liability arising out of or related to this Agreement shall be strictly capped at the total fees paid",
                            expected_status="VALID",
                        )
                    ],
                    is_grounded=True,
                ),
                GroundedEvalClaim(
                    claim_text="Indemnification claims under Section 3 are excluded from the general liability cap.",
                    citations=[
                        GroundedEvalCitation(
                            contract_id=c1_id,
                            chunk_id=str(ch2_id),
                            page_number=1,
                            verbatim_quote="Except for indemnification obligations under Section 3",
                            expected_status="VALID",
                        )
                    ],
                    is_grounded=True,
                ),
            ],
            description="Explicitly preserves distinct exceptions without blending them into a single ungrounded number.",
        ),
        # 17C & 17D (Failure Mode 12): Missing extracted facts
        GroundedEvalCase(
            case_id="case-15-missing-extracted-facts",
            title="Missing Extracted Facts / Out-of-Scope Term",
            query="What is the late payment penalty fee for NovaScale?",
            scope="single",
            contract_ids=[c1_id],
            expected_status="insufficient_evidence",
            expected_has_sufficient_evidence=False,
            failure_mode="missing_extracted_facts",
            mock_answer="The NovaScale agreement does not state any late payment fee percentage.",
            description="Query asks for a fact absent in NovaScale (present only in Apex).",
        ),
        # 17C & 17D (Failure Mode 13): Cross-contract contamination
        GroundedEvalCase(
            case_id="case-16-cross-contract-contamination",
            title="Cross-Contract Evidence Contamination Rejection",
            query="What are NovaScale's late payment penalties?",
            scope="single",
            contract_ids=[c1_id],
            expected_status="answered",
            expected_has_sufficient_evidence=True,
            failure_mode="cross_contract_contamination",
            mock_claims=[
                GroundedEvalClaim(
                    claim_text="Late payments incur a fee of 1.5% per month.",
                    citations=[
                        GroundedEvalCitation(
                            contract_id=c1_id,
                            chunk_id=str(ch7_id),  # Ch7 belongs to Apex (c2_id), not NovaScale
                            page_number=1,
                            verbatim_quote="Late payments incur a fee of 1.5% per month.",
                            expected_status="WRONG_CONTRACT",
                        )
                    ],
                    is_grounded=False,
                )
            ],
            description="Model improperly cited Apex's late fee chunk as proof for a NovaScale claim.",
        ),
    ]

    return GroundedEvaluationDataset(
        version="1.0",
        name="ContractIQ Grounded RAG Quality & Failure-Mode Benchmark",
        description="Deterministic benchmark suite covering supported claims, cross-contract QA, and 13 failure modes.",
        contracts=contracts,
        cases=cases,
    )

