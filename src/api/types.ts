/**
 * ContractIQ — API TypeScript Type Definitions
 * Aligned with backend schemas (Phases 1–13)
 */

export interface UserResponse {
  id: string;
  email: string;
  full_name: string | null;
  organization: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface ContractResponse {
  id: string;
  title: string;
  vendor: string | null;
  contract_type: string | null;
  status: string;
  effective_date: string | null;
  expiry_date: string | null;
  contract_value: number | null;
  currency: string;
  risk_level: string | null;
  has_auto_renewal: boolean | null;
  uploaded_by: string | null;
  file_name: string | null;
  page_count: number | null;
  processing_status: string;
  processing_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface ContractListResponse {
  items: ContractResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface ContractCreate {
  title: string;
  vendor?: string | null;
  contract_type?: string | null;
  status?: string;
  effective_date?: string | null;
  expiry_date?: string | null;
  contract_value?: number | null;
  currency?: string;
  risk_level?: string | null;
  has_auto_renewal?: boolean | null;
  page_count?: number | null;
  file_name?: string | null;
}

export interface ContractUploadResponse {
  contract_id: string;
  file_name: string;
  file_size: number;
  content_type: string;
  storage_key: string;
  processing_status: string;
  uploaded_at: string;
}

export interface EvidenceCitation {
  citation_index?: number;
  contract_id: string;
  page_number?: number;
  chunk_id?: string;
  clause_id?: string;
  snippet?: string;
  verdict?: string;
  verification_status?: string;
}

export interface AnswerClaim {
  claim_text: string;
  citation_indices: number[];
  is_supported: boolean;
}

export interface AnalystQueryResponse {
  query: string;
  answer: string;
  status: string;
  confidence_score: number;
  claims: AnswerClaim[];
  citations: EvidenceCitation[];
  queried_contract_ids: string[];
  retrieval_debug?: any;
}

export interface FieldComparisonRow {
  field_name: string;
  display_label: string;
  is_different: boolean;
  has_missing_values: boolean;
  difference_type: string;
  severity: string;
  variance_percentage?: number | null;
  day_difference?: number | null;
  values: Record<string, {
    raw_value: any;
    formatted_value: string;
    is_available: boolean;
    confidence_tier?: string;
    citations?: EvidenceCitation[];
  }>;
}

export interface ContractComparisonResponse {
  contracts: Array<{
    contract_id: string;
    title: string;
    vendor?: string;
    status?: string;
  }>;
  total_contracts_compared: number;
  comparison_timestamp: string;
  fields: FieldComparisonRow[];
  identical_fields_count: number;
  different_fields_count: number;
  critical_differences_count: number;
}

export interface ObligationDetailResponse {
  id: string;
  contract_id: string;
  clause_id: string;
  obligation_type: string;
  description: string;
  responsible_party?: string | null;
  due_date_raw?: string | null;
  is_recurring?: boolean | null;
  recurrence_frequency?: string | null;
  status?: string;
  priority?: string;
  created_at: string;
  derived_analysis?: {
    is_overdue: boolean;
    days_until_due?: number | null;
    cadence?: string | null;
    confidence_tier: string;
  };
  evidence_citations?: EvidenceCitation[];
}

export interface ObligationQueryResponse {
  contract_id: string;
  contract_title?: string;
  total_obligations: number;
  filtered_obligations: number;
  obligations: ObligationDetailResponse[];
  summary: {
    by_responsible_party: Record<string, number>;
    by_obligation_type: Record<string, number>;
    by_status: Record<string, number>;
    by_priority: Record<string, number>;
    recurring_count: number;
    non_recurring_count: number;
    overdue_count: number;
    upcoming_count: number;
  };
}

export interface RiskSignalResponse {
  id: string;
  contract_id: string;
  rule_id: string;
  rule_name: string;
  severity: string;
  category: string;
  description: string;
  reason: string;
  suggested_action?: string | null;
  evidence_id?: string | null;
  detected_at: string;
}

export interface RiskSignalListResponse {
  contract_id: string;
  signals: RiskSignalResponse[];
  total_signals: number;
  highest_severity: string;
  summary: {
    critical_count: number;
    high_count: number;
    medium_count: number;
    low_count: number;
  };
}
