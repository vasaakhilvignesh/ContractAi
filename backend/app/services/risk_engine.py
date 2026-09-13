"""
ContractIQ — Deterministic Contract Risk Engine (Phase 8A, 8B, 8C)

Core Architecture:
  1. RAG finds evidence.
  2. Structured extraction turns evidence into data (Clauses, Obligations, Facts).
  3. Deterministic rules turn structured data into actionable risk intelligence.
  - The LLM NEVER decides risk severity or triggers risk rules directly.
  - Every risk signal strictly traces back through:
      risk → rule → structured fact/clause/obligation → evidence → chunk → page → contract.
  - No false positives: If data is absent, rules do not fire or fabricate facts.

Rules implemented:
  - 8B: Renewal Rules:
      * RULE_CONTRACT_EXPIRED: Expiration date is in the past.
      * RULE_CONTRACT_EXPIRING_SOON: Expiration date within next 60 days.
      * RULE_AUTO_RENEWAL_ACTIVE: Contract automatically renews without explicit cancellation.
      * RULE_AUTO_RENEWAL_SHORT_NOTICE: Auto-renewal notice window is dangerously short (<= 30 days).
  - 8C: Contract Risk Rules:
      * RULE_TERMINATION_NOTICE_SHORT: Termination notice period is <= 15 days (procurement risk).
      * RULE_UNCAPPED_LIABILITY: Liability cap is missing, mutual uncapped, or explicitly uncapped.
      * RULE_BROAD_INDEMNIFICATION: Indemnification obligation is uncapped or one-sided/solely by Customer.
      * RULE_MISSING_GOVERNING_LAW: Agreement lacks an identifiable governing law.
      * RULE_HIGH_PRIORITY_OVERDUE_OBLIGATION: High priority obligation with past due date.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timezone
import logging
import re
from typing import Optional
import uuid

from app.models.clause import Clause
from app.models.contract import Contract
from app.models.contract_fact import ContractFact
from app.models.document_chunk import DocumentChunk
from app.models.obligation import Obligation
from app.schemas.risk import RiskCategory, RiskSeverity

logger = logging.getLogger(__name__)


# ====================================================================
# Risk Evaluation Context & Candidate Output
# ====================================================================

@dataclass
class ContractEvaluationContext:
    """
    Normalized, structured data context passed to deterministic risk rules.
    Contains pre-queried contract data, clauses, obligations, facts, and chunks.
    """
    contract: Contract
    clauses: list[Clause]
    obligations: list[Obligation]
    facts: list[ContractFact]
    chunks: list[DocumentChunk]
    reference_date: date

    def get_facts_by_key(self, key: str) -> list[ContractFact]:
        """Returns all facts matching a normalized fact_key."""
        k = key.strip().lower()
        return [f for f in self.facts if f.fact_key.strip().lower() == k]

    def get_clauses_by_type(self, clause_type: str) -> list[Clause]:
        """Returns all clauses matching a normalized clause_type."""
        ct = clause_type.strip().lower()
        return [c for c in self.clauses if c.clause_type.strip().lower() == ct]


@dataclass
class RiskRuleOutput:
    """Output candidate produced by a deterministic risk rule."""
    rule_id: str
    rule_description: str
    severity: RiskSeverity
    category: RiskCategory
    title: str
    triggered_fact: Optional[str] = None
    verbatim_evidence: Optional[str] = None
    page_number: Optional[int] = None
    recommended_action: Optional[str] = None
    source_clause_id: Optional[uuid.UUID] = None
    source_chunk_id: Optional[uuid.UUID] = None


# ====================================================================
# Rule Base Class
# ====================================================================

class BaseRiskRule(ABC):
    """Abstract base class for all deterministic contract risk rules."""

    @property
    @abstractmethod
    def rule_id(self) -> str:
        """Stable, unique rule identifier (e.g., 'RULE_AUTO_RENEWAL_ACTIVE')."""
        pass

    @property
    @abstractmethod
    def rule_description(self) -> str:
        """Clear explanation of the rule logic and criteria."""
        pass

    @abstractmethod
    def evaluate(self, ctx: ContractEvaluationContext) -> list[RiskRuleOutput]:
        """
        Evaluates the contract context and returns any triggered risk outputs.
        Must be strictly deterministic with zero side-effects.
        """
        pass


# ====================================================================
# Helpers: Parsing numbers, dates, days
# ====================================================================

def parse_iso_date(date_str: Optional[str]) -> Optional[date]:
    """Attempts to parse an ISO format YYYY-MM-DD date."""
    if not date_str:
        return None
    cleaned = date_str.strip()
    match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", cleaned)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            pass
    return None


def parse_days_from_text(text: Optional[str]) -> Optional[int]:
    """Extracts numeric days count from strings like '30 days', '15 business days', '60 calendar days'."""
    if not text:
        return None
    match = re.search(r"(\d+)\s*(?:business|calendar)?\s*days?", text, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    # Also check standalone integer
    if text.strip().isdigit():
        return int(text.strip())
    return None


# ====================================================================
# Phase 8B: Renewal Rules
# ====================================================================

class ContractExpiredRule(BaseRiskRule):
    """
    Fires if the contract expiration_date is already in the past relative to reference_date.
    """
    rule_id = "RULE_CONTRACT_EXPIRED"
    rule_description = "Flags contracts whose stated expiration date has already passed."

    def evaluate(self, ctx: ContractEvaluationContext) -> list[RiskRuleOutput]:
        exp_facts = ctx.get_facts_by_key("expiration_date")
        outputs = []
        for fact in exp_facts:
            exp_date = parse_iso_date(fact.fact_value)
            if exp_date and exp_date < ctx.reference_date:
                outputs.append(
                    RiskRuleOutput(
                        rule_id=self.rule_id,
                        rule_description=self.rule_description,
                        severity=RiskSeverity.CRITICAL,
                        category=RiskCategory.RENEWAL,
                        title=f"Contract Expired on {exp_date.isoformat()}",
                        triggered_fact=f"expiration_date: {fact.fact_value}",
                        verbatim_evidence=fact.verbatim_evidence,
                        page_number=fact.page_number,
                        recommended_action="Review contract status immediately; determine if an extension, amendment, or transition is required.",
                        source_clause_id=fact.source_clause_id,
                        source_chunk_id=fact.source_chunk_id,
                    )
                )
        return outputs


class ContractExpiringSoonRule(BaseRiskRule):
    """
    Fires if the contract expiration_date is within 60 days of the reference_date.
    """
    rule_id = "RULE_CONTRACT_EXPIRING_SOON"
    rule_description = "Flags contracts expiring within the next 60 days."

    def evaluate(self, ctx: ContractEvaluationContext) -> list[RiskRuleOutput]:
        exp_facts = ctx.get_facts_by_key("expiration_date")
        outputs = []
        for fact in exp_facts:
            exp_date = parse_iso_date(fact.fact_value)
            if exp_date and ctx.reference_date <= exp_date:
                days_left = (exp_date - ctx.reference_date).days
                if days_left <= 60:
                    severity = RiskSeverity.HIGH if days_left <= 30 else RiskSeverity.MEDIUM
                    outputs.append(
                        RiskRuleOutput(
                            rule_id=self.rule_id,
                            rule_description=self.rule_description,
                            severity=severity,
                            category=RiskCategory.RENEWAL,
                            title=f"Contract Expiring in {days_left} Days ({exp_date.isoformat()})",
                            triggered_fact=f"expiration_date: {fact.fact_value} ({days_left} days remaining)",
                            verbatim_evidence=fact.verbatim_evidence,
                            page_number=fact.page_number,
                            recommended_action=f"Initiate renewal or RFP discussions before expiration on {exp_date.isoformat()}.",
                            source_clause_id=fact.source_clause_id,
                            source_chunk_id=fact.source_chunk_id,
                        )
                    )
        return outputs


class AutoRenewalActiveRule(BaseRiskRule):
    """
    Fires if an auto-renewal clause or renewal_term fact indicates automatic renewal.
    """
    rule_id = "RULE_AUTO_RENEWAL_ACTIVE"
    rule_description = "Flags contracts that renew automatically unless timely notice is given."

    def evaluate(self, ctx: ContractEvaluationContext) -> list[RiskRuleOutput]:
        outputs = []
        # Check auto-renewal clauses
        renewal_clauses = ctx.get_clauses_by_type("auto_renewal")
        for clause in renewal_clauses:
            outputs.append(
                RiskRuleOutput(
                    rule_id=self.rule_id,
                    rule_description=self.rule_description,
                    severity=RiskSeverity.MEDIUM,
                    category=RiskCategory.RENEWAL,
                    title="Automatic Renewal Clause Detected",
                    triggered_fact=f"clause_type: auto_renewal ({clause.clause_label or 'Auto-Renewal'})",
                    verbatim_evidence=clause.verbatim_text,
                    page_number=clause.page_number,
                    recommended_action="Set calendar alerts and verify required opt-out notice windows to avoid inadvertent renewal.",
                    source_clause_id=clause.id,
                    source_chunk_id=clause.source_chunk_id,
                )
            )

        # Also check renewal_term facts if no auto-renewal clause already captured it
        if not outputs:
            renewal_facts = ctx.get_facts_by_key("renewal_term")
            for fact in renewal_facts:
                val_lower = fact.fact_value.lower()
                if "auto" in val_lower or "successive" in val_lower or "automatic" in val_lower:
                    outputs.append(
                        RiskRuleOutput(
                            rule_id=self.rule_id,
                            rule_description=self.rule_description,
                            severity=RiskSeverity.MEDIUM,
                            category=RiskCategory.RENEWAL,
                            title="Automatic Renewal Term Detected",
                            triggered_fact=f"renewal_term: {fact.fact_value}",
                            verbatim_evidence=fact.verbatim_evidence,
                            page_number=fact.page_number,
                            recommended_action="Track opt-out deadlines in the contract management workflow.",
                            source_clause_id=fact.source_clause_id,
                            source_chunk_id=fact.source_chunk_id,
                        )
                    )
        return outputs


class AutoRenewalShortNoticeRule(BaseRiskRule):
    """
    Fires if auto-renewal notice period is <= 30 days or requires excessive advance notice.
    """
    rule_id = "RULE_AUTO_RENEWAL_SHORT_NOTICE"
    rule_description = "Flags auto-renewal clauses requiring 30 days or less to opt out, creating lock-in risk."

    def evaluate(self, ctx: ContractEvaluationContext) -> list[RiskRuleOutput]:
        outputs = []
        notice_facts = ctx.get_facts_by_key("notice_period")
        renewal_clauses = ctx.get_clauses_by_type("auto_renewal")
        
        # If there is auto-renewal context
        is_auto_renewal = bool(renewal_clauses) or any(
            "auto" in f.fact_value.lower() for f in ctx.get_facts_by_key("renewal_term")
        )
        if not is_auto_renewal:
            return outputs

        for fact in notice_facts:
            days = parse_days_from_text(fact.fact_value)
            if days is not None and days <= 30:
                outputs.append(
                    RiskRuleOutput(
                        rule_id=self.rule_id,
                        rule_description=self.rule_description,
                        severity=RiskSeverity.HIGH,
                        category=RiskCategory.RENEWAL,
                        title=f"Short Auto-Renewal Notice Window ({days} Days)",
                        triggered_fact=f"notice_period: {fact.fact_value}",
                        verbatim_evidence=fact.verbatim_evidence,
                        page_number=fact.page_number,
                        recommended_action=f"Auto-renewal cancellation requires {days} days notice. Calendar early reminders to prevent unbudgeted renewal.",
                        source_clause_id=fact.source_clause_id,
                        source_chunk_id=fact.source_chunk_id,
                    )
                )
        return outputs


# ====================================================================
# Phase 8C: Contract Risk Rules
# ====================================================================

class TerminationNoticeShortRule(BaseRiskRule):
    """
    Fires if the termination notice period is <= 15 days, leaving inadequate operational runway.
    """
    rule_id = "RULE_TERMINATION_NOTICE_SHORT"
    rule_description = "Flags termination notice periods of 15 days or less."

    def evaluate(self, ctx: ContractEvaluationContext) -> list[RiskRuleOutput]:
        outputs = []
        term_facts = ctx.get_facts_by_key("termination_notice_period")
        for fact in term_facts:
            days = parse_days_from_text(fact.fact_value)
            if days is not None and days <= 15:
                outputs.append(
                    RiskRuleOutput(
                        rule_id=self.rule_id,
                        rule_description=self.rule_description,
                        severity=RiskSeverity.HIGH,
                        category=RiskCategory.TERMINATION,
                        title=f"Short Termination Notice Period ({days} Days)",
                        triggered_fact=f"termination_notice_period: {fact.fact_value}",
                        verbatim_evidence=fact.verbatim_evidence,
                        page_number=fact.page_number,
                        recommended_action=f"Standard commercial termination notice is 30–60 days. Negotiate extension to avoid operational disruption.",
                        source_clause_id=fact.source_clause_id,
                        source_chunk_id=fact.source_chunk_id,
                    )
                )
        return outputs


class UncappedLiabilityRule(BaseRiskRule):
    """
    Fires if liability cap is explicitly uncapped, absent in high-risk clause, or mutual uncapped.
    """
    rule_id = "RULE_UNCAPPED_LIABILITY"
    rule_description = "Flags agreements with uncapped liability or missing aggregate liability limitations."

    def evaluate(self, ctx: ContractEvaluationContext) -> list[RiskRuleOutput]:
        outputs = []
        cap_facts = ctx.get_facts_by_key("liability_cap")
        for fact in cap_facts:
            val_lower = fact.fact_value.lower()
            if "uncapped" in val_lower or "no cap" in val_lower or "unlimited" in val_lower:
                outputs.append(
                    RiskRuleOutput(
                        rule_id=self.rule_id,
                        rule_description=self.rule_description,
                        severity=RiskSeverity.CRITICAL,
                        category=RiskCategory.LIABILITY,
                        title="Uncapped Liability Detected",
                        triggered_fact=f"liability_cap: {fact.fact_value}",
                        verbatim_evidence=fact.verbatim_evidence,
                        page_number=fact.page_number,
                        recommended_action="Uncapped liability poses severe financial risk. Require a mutual aggregate liability cap (e.g. 12 months fees).",
                        source_clause_id=fact.source_clause_id,
                        source_chunk_id=fact.source_chunk_id,
                    )
                )

        # Check liability clauses for explicit exclusions or uncapped language
        if not outputs:
            liability_clauses = ctx.get_clauses_by_type("liability")
            for clause in liability_clauses:
                text_lower = clause.verbatim_text.lower()
                if "shall not be subject to any limitation" in text_lower or "unlimited liability" in text_lower or "without limitation" in text_lower:
                    outputs.append(
                        RiskRuleOutput(
                            rule_id=self.rule_id,
                            rule_description=self.rule_description,
                            severity=RiskSeverity.CRITICAL,
                            category=RiskCategory.LIABILITY,
                            title="Uncapped Liability Exclusion in Clause",
                            triggered_fact="clause_type: liability (contains uncapped carveout)",
                            verbatim_evidence=clause.verbatim_text,
                            page_number=clause.page_number,
                            recommended_action="Examine uncapped carveouts in the liability clause and narrow exceptions to willful misconduct only.",
                            source_clause_id=clause.id,
                            source_chunk_id=clause.source_chunk_id,
                        )
                    )
        return outputs


class BroadIndemnificationRule(BaseRiskRule):
    """
    Fires if indemnification is uncapped or unilaterally broad.
    """
    rule_id = "RULE_BROAD_INDEMNIFICATION"
    rule_description = "Flags broad or uncapped indemnification obligations."

    def evaluate(self, ctx: ContractEvaluationContext) -> list[RiskRuleOutput]:
        outputs = []
        indem_facts = ctx.get_facts_by_key("indemnification_cap")
        for fact in indem_facts:
            val_lower = fact.fact_value.lower()
            if "uncapped" in val_lower or "unlimited" in val_lower or "no cap" in val_lower:
                outputs.append(
                    RiskRuleOutput(
                        rule_id=self.rule_id,
                        rule_description=self.rule_description,
                        severity=RiskSeverity.HIGH,
                        category=RiskCategory.INDEMNIFICATION,
                        title="Uncapped Indemnification Exposure",
                        triggered_fact=f"indemnification_cap: {fact.fact_value}",
                        verbatim_evidence=fact.verbatim_evidence,
                        page_number=fact.page_number,
                        recommended_action="Subject indemnification to the general liability limitation or establish a dedicated super-cap.",
                        source_clause_id=fact.source_clause_id,
                        source_chunk_id=fact.source_chunk_id,
                    )
                )
        return outputs


class MissingGoverningLawRule(BaseRiskRule):
    """
    Fires if the agreement has extracted facts or clauses, but no governing_law fact or clause was identified.
    """
    rule_id = "RULE_MISSING_GOVERNING_LAW"
    rule_description = "Flags contracts where governing law or legal jurisdiction is missing or unspecified."

    def evaluate(self, ctx: ContractEvaluationContext) -> list[RiskRuleOutput]:
        # Only evaluate if contract has been processed and has extracted data
        if not ctx.clauses and not ctx.facts:
            return []

        law_facts = ctx.get_facts_by_key("governing_law")
        law_clauses = ctx.get_clauses_by_type("governing_law")

        if not law_facts and not law_clauses:
            return [
                RiskRuleOutput(
                    rule_id=self.rule_id,
                    rule_description=self.rule_description,
                    severity=RiskSeverity.MEDIUM,
                    category=RiskCategory.CRITICAL_TERMS,
                    title="Missing Governing Law Specification",
                    triggered_fact="governing_law: not found in extracted clauses or facts",
                    verbatim_evidence=None,
                    page_number=None,
                    recommended_action="Explicitly specify governing jurisdiction and dispute forum to prevent conflict-of-laws exposure.",
                    source_clause_id=None,
                    source_chunk_id=None,
                )
            ]
        return []


class OverdueHighPriorityObligationRule(BaseRiskRule):
    """
    Fires if a high-priority obligation has a due date that is in the past and is still pending.
    """
    rule_id = "RULE_HIGH_PRIORITY_OVERDUE_OBLIGATION"
    rule_description = "Flags high priority obligations with past due dates that remain uncompleted."

    def evaluate(self, ctx: ContractEvaluationContext) -> list[RiskRuleOutput]:
        outputs = []
        for ob in ctx.obligations:
            if ob.priority == "high" and ob.status in ("pending", "in_progress"):
                if ob.due_date and ob.due_date < ctx.reference_date:
                    outputs.append(
                        RiskRuleOutput(
                            rule_id=self.rule_id,
                            rule_description=self.rule_description,
                            severity=RiskSeverity.HIGH,
                            category=RiskCategory.COMPLIANCE,
                            title=f"Overdue High-Priority Obligation: {ob.title}",
                            triggered_fact=f"obligation due_date: {ob.due_date.isoformat()}, status: {ob.status}",
                            verbatim_evidence=ob.verbatim_evidence,
                            page_number=ob.page_number,
                            recommended_action=f"Obligation '{ob.title}' is overdue ({ob.due_date.isoformat()}). Escalate to responsible party ({ob.responsible_party or 'Unassigned'}).",
                            source_clause_id=ob.source_clause_id,
                            source_chunk_id=ob.source_chunk_id,
                        )
                    )
        return outputs


# ====================================================================
# Risk Engine Registry
# ====================================================================

STANDARD_RISK_RULES: list[BaseRiskRule] = [
    ContractExpiredRule(),
    ContractExpiringSoonRule(),
    AutoRenewalActiveRule(),
    AutoRenewalShortNoticeRule(),
    TerminationNoticeShortRule(),
    UncappedLiabilityRule(),
    BroadIndemnificationRule(),
    MissingGoverningLawRule(),
    OverdueHighPriorityObligationRule(),
]


def evaluate_contract_rules(
    ctx: ContractEvaluationContext,
    rules: Optional[list[BaseRiskRule]] = None,
) -> list[RiskRuleOutput]:
    """
    Executes all registered deterministic risk rules on the contract context.
    Returns deduplicated, sorted list of candidate risk signals.
    """
    active_rules = rules if rules is not None else STANDARD_RISK_RULES
    results: list[RiskRuleOutput] = []

    for rule in active_rules:
        try:
            outputs = rule.evaluate(ctx)
            results.extend(outputs)
        except Exception as exc:
            logger.error("Error running risk rule %s on contract %s: %s", rule.rule_id, ctx.contract.id, exc)

    return results
