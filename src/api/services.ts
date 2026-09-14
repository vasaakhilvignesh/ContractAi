/**
 * ContractIQ — Service Endpoints Implementation
 */

import { apiRequest } from "./client";
import type {
  UserResponse,
  TokenResponse,
  ContractResponse,
  ContractListResponse,
  ContractCreate,
  ContractUploadResponse,
  AnalystQueryResponse,
  ContractComparisonResponse,
  ObligationQueryResponse,
  RiskSignalListResponse,
} from "./types";

export const authApi = {
  register: (data: { email: string; password: string; full_name?: string; organization?: string }) =>
    apiRequest<UserResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  login: (data: { email: string; password: string }) =>
    apiRequest<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getMe: () => apiRequest<UserResponse>("/auth/me"),
};

export const contractsApi = {
  list: (params?: { offset?: number; limit?: number; status?: string; vendor?: string; risk_level?: string }) => {
    const query = new URLSearchParams();
    if (params?.offset !== undefined) query.set("offset", String(params.offset));
    if (params?.limit !== undefined) query.set("limit", String(params.limit));
    if (params?.status) query.set("status", params.status);
    if (params?.vendor) query.set("vendor", params.vendor);
    if (params?.risk_level) query.set("risk_level", params.risk_level);
    const queryString = query.toString();
    return apiRequest<ContractListResponse>(`/contracts${queryString ? `?${queryString}` : ""}`);
  },

  get: (contractId: string) => apiRequest<ContractResponse>(`/contracts/${contractId}`),

  create: (data: ContractCreate) =>
    apiRequest<ContractResponse>("/contracts", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  update: (contractId: string, data: Partial<ContractCreate>) =>
    apiRequest<ContractResponse>(`/contracts/${contractId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  delete: (contractId: string) =>
    apiRequest<void>(`/contracts/${contractId}`, {
      method: "DELETE",
    }),

  uploadPdf: (contractId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiRequest<ContractUploadResponse>(`/contracts/${contractId}/upload`, {
      method: "POST",
      body: formData,
    });
  },

  extractText: (contractId: string) =>
    apiRequest<any>(`/contracts/${contractId}/extract`, {
      method: "POST",
    }),

  chunk: (contractId: string) =>
    apiRequest<any>(`/contracts/${contractId}/chunk`, {
      method: "POST",
    }),

  embed: (contractId: string) =>
    apiRequest<any>(`/contracts/${contractId}/embed`, {
      method: "POST",
    }),

  extractClauses: (contractId: string) =>
    apiRequest<any>(`/contracts/${contractId}/clauses/extract`, {
      method: "POST",
    }),

  extractObligations: (contractId: string) =>
    apiRequest<any>(`/contracts/${contractId}/obligations/extract`, {
      method: "POST",
    }),

  extractFacts: (contractId: string) =>
    apiRequest<any>(`/contracts/${contractId}/facts/extract`, {
      method: "POST",
    }),

  evaluateRisks: (contractId: string) =>
    apiRequest<any>(`/contracts/${contractId}/risks/evaluate`, {
      method: "POST",
    }),

  getRisks: (contractId: string) =>
    apiRequest<RiskSignalListResponse>(`/contracts/${contractId}/risks`),
};

export const analystApi = {
  query: (data: { contract_ids: string[]; query: string; top_k_per_contract?: number; include_debug?: boolean }) =>
    apiRequest<AnalystQueryResponse>("/analyst/query", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

export const comparisonApi = {
  compare: (data: { contract_ids: string[]; comparison_fields?: string[]; include_evidence?: boolean }) =>
    apiRequest<ContractComparisonResponse>("/contracts/compare", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

export const obligationsApi = {
  query: (contractId: string, params?: {
    responsible_party?: string;
    obligation_type?: string;
    status?: string;
    priority?: string;
    is_recurring?: boolean;
    is_overdue?: boolean;
    has_due_date?: boolean;
  }) => {
    const query = new URLSearchParams();
    if (params?.responsible_party) query.set("responsible_party", params.responsible_party);
    if (params?.obligation_type) query.set("obligation_type", params.obligation_type);
    if (params?.status) query.set("status", params.status);
    if (params?.priority) query.set("priority", params.priority);
    if (params?.is_recurring !== undefined) query.set("is_recurring", String(params.is_recurring));
    if (params?.is_overdue !== undefined) query.set("is_overdue", String(params.is_overdue));
    if (params?.has_due_date !== undefined) query.set("has_due_date", String(params.has_due_date));
    const queryString = query.toString();
    return apiRequest<ObligationQueryResponse>(`/contracts/${contractId}/obligations/query${queryString ? `?${queryString}` : ""}`);
  },

  getDetail: (contractId: string, obligationId: string) =>
    apiRequest<any>(`/contracts/${contractId}/obligations/${obligationId}`),
};
