export type RiskLevel = "critical" | "high" | "medium" | "low" | "none";
export type ContractStatus = "active" | "expired" | "draft" | "under_review" | "terminated";
export type ProcessingStatus = "complete" | "processing" | "failed" | "pending";

export interface Contract {
  id: string;
  name: string;
  vendor: string;
  type: string;
  status: ContractStatus;
  riskLevel: RiskLevel;
  renewalDate: string;
  effectiveDate: string;
  expirationDate: string;
  obligations: number;
  lastUpdated: string;
  processingStatus: ProcessingStatus;
  pages: number;
  value: string;
  noticePeriod: string;
}

export interface Risk {
  id: string;
  contractId: string;
  contractName: string;
  vendor: string;
  severity: RiskLevel;
  type: string;
  rule: string;
  summary: string;
  extractedFact: string;
  sourceClause: string;
  sourcePage: number;
  evidenceSnippet: string;
  detectedDate: string;
  status: "open" | "reviewed" | "accepted" | "resolved";
  recommendedAction: string;
}

export interface Obligation {
  id: string;
  contractId: string;
  contractName: string;
  vendor: string;
  description: string;
  responsibleParty: string;
  dueDate: string;
  frequency: string;
  priority: "critical" | "high" | "medium" | "low";
  status: "pending" | "due_soon" | "overdue" | "completed" | "waived";
  sourceClause: string;
  sourcePage: number;
  evidence: string;
}

export interface AuditEvent {
  id: string;
  timestamp: string;
  user: string;
  userEmail: string;
  action: string;
  resource: string;
  status: "success" | "failed" | "warning";
  ip: string;
}

export const contracts: Contract[] = [
  {
    id: "c001",
    name: "Master Services Agreement — Salesforce",
    vendor: "Salesforce Inc.",
    type: "MSA",
    status: "active",
    riskLevel: "high",
    renewalDate: "2024-03-15",
    effectiveDate: "2022-03-15",
    expirationDate: "2024-03-15",
    obligations: 14,
    lastUpdated: "2024-01-08",
    processingStatus: "complete",
    pages: 47,
    value: "$240,000/yr",
    noticePeriod: "30 days",
  },
  {
    id: "c002",
    name: "SaaS Subscription Agreement — AWS",
    vendor: "Amazon Web Services",
    type: "SaaS",
    status: "active",
    riskLevel: "medium",
    renewalDate: "2024-06-01",
    effectiveDate: "2023-06-01",
    expirationDate: "2024-06-01",
    obligations: 8,
    lastUpdated: "2024-01-05",
    processingStatus: "complete",
    pages: 32,
    value: "$85,000/yr",
    noticePeriod: "60 days",
  },
  {
    id: "c003",
    name: "Professional Services Agreement — Accenture",
    vendor: "Accenture LLP",
    type: "PSA",
    status: "active",
    riskLevel: "critical",
    renewalDate: "2024-02-28",
    effectiveDate: "2021-02-28",
    expirationDate: "2024-02-28",
    obligations: 22,
    lastUpdated: "2024-01-10",
    processingStatus: "complete",
    pages: 68,
    value: "$1,200,000",
    noticePeriod: "15 days",
  },
  {
    id: "c004",
    name: "Data Processing Agreement — Snowflake",
    vendor: "Snowflake Inc.",
    type: "DPA",
    status: "active",
    riskLevel: "low",
    renewalDate: "2025-01-01",
    effectiveDate: "2023-01-01",
    expirationDate: "2025-01-01",
    obligations: 6,
    lastUpdated: "2024-01-02",
    processingStatus: "complete",
    pages: 24,
    value: "$42,000/yr",
    noticePeriod: "90 days",
  },
  {
    id: "c005",
    name: "License Agreement — Adobe",
    vendor: "Adobe Systems",
    type: "License",
    status: "active",
    riskLevel: "medium",
    renewalDate: "2024-04-22",
    effectiveDate: "2023-04-22",
    expirationDate: "2024-04-22",
    obligations: 4,
    lastUpdated: "2023-12-20",
    processingStatus: "complete",
    pages: 18,
    value: "$28,000/yr",
    noticePeriod: "30 days",
  },
  {
    id: "c006",
    name: "Non-Disclosure Agreement — Stripe",
    vendor: "Stripe Inc.",
    type: "NDA",
    status: "active",
    riskLevel: "none",
    renewalDate: "2026-05-10",
    effectiveDate: "2024-05-10",
    expirationDate: "2026-05-10",
    obligations: 3,
    lastUpdated: "2024-01-01",
    processingStatus: "complete",
    pages: 8,
    value: "N/A",
    noticePeriod: "N/A",
  },
  {
    id: "c007",
    name: "Enterprise License — Microsoft 365",
    vendor: "Microsoft Corporation",
    type: "License",
    status: "under_review",
    riskLevel: "high",
    renewalDate: "2024-03-01",
    effectiveDate: "2023-03-01",
    expirationDate: "2024-03-01",
    obligations: 11,
    lastUpdated: "2024-01-09",
    processingStatus: "complete",
    pages: 55,
    value: "$320,000/yr",
    noticePeriod: "30 days",
  },
  {
    id: "c008",
    name: "Consulting Agreement — McKinsey",
    vendor: "McKinsey & Company",
    type: "Consulting",
    status: "active",
    riskLevel: "high",
    renewalDate: "2024-05-15",
    effectiveDate: "2023-05-15",
    expirationDate: "2024-05-15",
    obligations: 9,
    lastUpdated: "2024-01-07",
    processingStatus: "complete",
    pages: 41,
    value: "$480,000",
    noticePeriod: "45 days",
  },
];

export const risks: Risk[] = [
  {
    id: "r001",
    contractId: "c003",
    contractName: "Professional Services Agreement — Accenture",
    vendor: "Accenture LLP",
    severity: "critical",
    type: "Short Notice Period",
    rule: "Notice period < 30 days triggers critical flag",
    summary: "Contract notice period of 15 days is critically short for a $1.2M engagement, leaving insufficient time for vendor transition.",
    extractedFact: "Notice period: 15 calendar days",
    sourceClause: "Section 12.3 — Termination for Convenience",
    sourcePage: 34,
    evidenceSnippet: "\"Either party may terminate this Agreement for convenience upon fifteen (15) calendar days written notice to the other party.\"",
    detectedDate: "2024-01-10",
    status: "open",
    recommendedAction: "Negotiate notice period extension to minimum 60 days before next renewal. Flag for legal review.",
  },
  {
    id: "r002",
    contractId: "c001",
    contractName: "Master Services Agreement — Salesforce",
    vendor: "Salesforce Inc.",
    severity: "high",
    type: "Auto Renewal",
    rule: "Auto-renewal without explicit opt-out window detected",
    summary: "Contract auto-renews for 12-month terms unless terminated 30 days before expiry. Renewal is March 15, 2024.",
    extractedFact: "Auto-renewal: Yes. Renewal term: 12 months. Notice required: 30 days prior.",
    sourceClause: "Section 4.2 — Renewal Terms",
    sourcePage: 12,
    evidenceSnippet: "\"This Agreement shall automatically renew for successive one (1) year periods unless either party provides written notice of non-renewal at least thirty (30) days prior to the end of the then-current term.\"",
    detectedDate: "2024-01-08",
    status: "open",
    recommendedAction: "Decision required by February 14, 2024. Contact Salesforce account team to negotiate terms.",
  },
  {
    id: "r003",
    contractId: "c007",
    contractName: "Enterprise License — Microsoft 365",
    vendor: "Microsoft Corporation",
    severity: "high",
    type: "High Liability Exposure",
    rule: "Uncapped liability clause detected",
    summary: "Mutual indemnification clause has no liability cap, exposing the company to potentially unlimited claims.",
    extractedFact: "Liability cap: None specified for IP indemnification claims",
    sourceClause: "Section 18.1 — Indemnification",
    sourcePage: 41,
    evidenceSnippet: "\"Microsoft shall indemnify, defend and hold harmless Customer from and against any and all claims... arising out of or related to any allegation that the Software infringes any third-party intellectual property rights.\"",
    detectedDate: "2024-01-09",
    status: "reviewed",
    recommendedAction: "Request liability cap amendment equal to 12 months of fees paid.",
  },
  {
    id: "r004",
    contractId: "c008",
    contractName: "Consulting Agreement — McKinsey",
    vendor: "McKinsey & Company",
    severity: "high",
    type: "Termination Restriction",
    rule: "Termination for convenience with fee penalty detected",
    summary: "Early termination requires payment of 25% of remaining contract value as a termination fee.",
    extractedFact: "Early termination fee: 25% of remaining contract value",
    sourceClause: "Section 9.4 — Early Termination Fees",
    sourcePage: 28,
    evidenceSnippet: "\"In the event of early termination for convenience, Client shall pay Consultant a termination fee equal to twenty-five percent (25%) of the fees remaining under the Statement of Work.\"",
    detectedDate: "2024-01-07",
    status: "open",
    recommendedAction: "Calculate potential exposure. Consider negotiating to a flat fee or milestone-based termination.",
  },
  {
    id: "r005",
    contractId: "c002",
    contractName: "SaaS Subscription Agreement — AWS",
    vendor: "Amazon Web Services",
    severity: "medium",
    type: "Payment Risk",
    rule: "Late payment penalty exceeds 2% per month",
    summary: "Late payment penalty of 1.5% per month (18% annually) applies after 30-day grace period.",
    extractedFact: "Late payment penalty: 1.5% per month after 30 days",
    sourceClause: "Section 7.3 — Payment Terms",
    sourcePage: 19,
    evidenceSnippet: "\"Amounts not paid within thirty (30) days of invoice date shall bear interest at the rate of one and one-half percent (1.5%) per month.\"",
    detectedDate: "2024-01-05",
    status: "accepted",
    recommendedAction: "Ensure AP processes invoices within 25-day window to avoid penalties.",
  },
  {
    id: "r006",
    contractId: "c005",
    contractName: "License Agreement — Adobe",
    vendor: "Adobe Systems",
    severity: "medium",
    type: "Auto Renewal",
    rule: "Auto-renewal without explicit opt-out window detected",
    summary: "License auto-renews April 22. Only 30-day notice window remains for non-renewal decision.",
    extractedFact: "Auto-renewal: Yes. Next renewal: April 22, 2024",
    sourceClause: "Section 3.1 — Subscription Term",
    sourcePage: 7,
    evidenceSnippet: "\"Subscriptions automatically renew for successive annual terms unless cancelled at least thirty (30) days before renewal.\"",
    detectedDate: "2024-01-06",
    status: "open",
    recommendedAction: "Review license utilization before March 22 decision deadline.",
  },
  {
    id: "r007",
    contractId: "c004",
    contractName: "Data Processing Agreement — Snowflake",
    vendor: "Snowflake Inc.",
    severity: "low",
    type: "Missing Protection Clause",
    rule: "GDPR right to erasure acknowledgment missing",
    summary: "DPA does not explicitly address GDPR Article 17 right-to-erasure obligations for sub-processors.",
    extractedFact: "Right to erasure clause: Not found",
    sourceClause: "Section 5 — Data Subject Rights",
    sourcePage: 11,
    evidenceSnippet: "\"Processor shall assist Controller in responding to requests from data subjects... [Article 15, 16, 18, 21 listed; Article 17 absent]\"",
    detectedDate: "2024-01-02",
    status: "open",
    recommendedAction: "Request DPA amendment to include explicit Article 17 erasure obligations.",
  },
];

export const obligations: Obligation[] = [
  {
    id: "o001",
    contractId: "c001",
    contractName: "Master Services Agreement — Salesforce",
    vendor: "Salesforce Inc.",
    description: "Provide written notice of non-renewal at least 30 days before contract expiration",
    responsibleParty: "Procurement",
    dueDate: "2024-02-14",
    frequency: "One-time",
    priority: "critical",
    status: "due_soon",
    sourceClause: "Section 4.2 — Renewal Terms",
    sourcePage: 12,
    evidence: "Auto-renewal unless 30-day prior written notice provided before March 15, 2024.",
  },
  {
    id: "o002",
    contractId: "c003",
    contractName: "Professional Services Agreement — Accenture",
    vendor: "Accenture LLP",
    description: "Submit monthly progress report by 5th of each month",
    responsibleParty: "Project Management",
    dueDate: "2024-02-05",
    frequency: "Monthly",
    priority: "high",
    status: "due_soon",
    sourceClause: "Section 6.1 — Reporting Requirements",
    sourcePage: 18,
    evidence: "Client shall provide written monthly status reports within five (5) business days of each calendar month end.",
  },
  {
    id: "o003",
    contractId: "c002",
    contractName: "SaaS Subscription Agreement — AWS",
    vendor: "Amazon Web Services",
    description: "Complete annual security assessment and share SOC 2 report",
    responsibleParty: "Security Team",
    dueDate: "2024-06-01",
    frequency: "Annual",
    priority: "high",
    status: "pending",
    sourceClause: "Section 11.2 — Security Compliance",
    sourcePage: 28,
    evidence: "Customer shall maintain SOC 2 Type II compliance and provide updated reports upon renewal.",
  },
  {
    id: "o004",
    contractId: "c007",
    contractName: "Enterprise License — Microsoft 365",
    vendor: "Microsoft Corporation",
    description: "Conduct quarterly license reconciliation and report over/under usage",
    responsibleParty: "IT Operations",
    dueDate: "2024-03-31",
    frequency: "Quarterly",
    priority: "medium",
    status: "pending",
    sourceClause: "Section 8.3 — License Compliance",
    sourcePage: 32,
    evidence: "Licensee shall conduct quarterly reconciliation of deployed licenses versus purchased seats.",
  },
  {
    id: "o005",
    contractId: "c003",
    contractName: "Professional Services Agreement — Accenture",
    vendor: "Accenture LLP",
    description: "Approve or reject deliverable within 10 business days of submission",
    responsibleParty: "Procurement",
    dueDate: "2024-01-25",
    frequency: "Per deliverable",
    priority: "high",
    status: "overdue",
    sourceClause: "Section 7.2 — Acceptance Criteria",
    sourcePage: 22,
    evidence: "Client has ten (10) business days from delivery to provide written acceptance or rejection with specific objections.",
  },
  {
    id: "o006",
    contractId: "c004",
    contractName: "Data Processing Agreement — Snowflake",
    vendor: "Snowflake Inc.",
    description: "Update data retention policy and notify Snowflake of any changes",
    responsibleParty: "Legal / Privacy",
    dueDate: "2024-03-01",
    frequency: "Annual",
    priority: "medium",
    status: "pending",
    sourceClause: "Section 4.3 — Data Retention",
    sourcePage: 9,
    evidence: "Controller shall maintain and communicate current data retention schedules annually or upon material change.",
  },
  {
    id: "o007",
    contractId: "c008",
    contractName: "Consulting Agreement — McKinsey",
    vendor: "McKinsey & Company",
    description: "Process invoice payment within 30 days of receipt",
    responsibleParty: "Finance / AP",
    dueDate: "2024-02-01",
    frequency: "Per invoice",
    priority: "high",
    status: "due_soon",
    sourceClause: "Section 7.1 — Payment Terms",
    sourcePage: 23,
    evidence: "Client agrees to pay all undisputed invoices within thirty (30) days of invoice date.",
  },
  {
    id: "o008",
    contractId: "c001",
    contractName: "Master Services Agreement — Salesforce",
    vendor: "Salesforce Inc.",
    description: "Submit annual data export for compliance backup",
    responsibleParty: "IT Operations",
    dueDate: "2024-03-01",
    frequency: "Annual",
    priority: "medium",
    status: "completed",
    sourceClause: "Section 14.2 — Data Portability",
    sourcePage: 39,
    evidence: "Customer shall export all Customer Data at least annually for business continuity purposes.",
  },
];

export const auditEvents: AuditEvent[] = [
  {
    id: "a001",
    timestamp: "2024-01-10 14:32:07",
    user: "Sarah Chen",
    userEmail: "s.chen@company.com",
    action: "Contract uploaded",
    resource: "Professional Services Agreement — Accenture",
    status: "success",
    ip: "10.0.1.42",
  },
  {
    id: "a002",
    timestamp: "2024-01-10 14:35:22",
    user: "Sarah Chen",
    userEmail: "s.chen@company.com",
    action: "AI question submitted",
    resource: "AI Analyst — 'What is the termination notice period for Accenture?'",
    status: "success",
    ip: "10.0.1.42",
  },
  {
    id: "a003",
    timestamp: "2024-01-10 11:18:44",
    user: "Marcus Webb",
    userEmail: "m.webb@company.com",
    action: "Risk reviewed",
    resource: "R-003: High Liability Exposure — Microsoft 365",
    status: "success",
    ip: "10.0.2.18",
  },
  {
    id: "a004",
    timestamp: "2024-01-09 16:52:11",
    user: "Marcus Webb",
    userEmail: "m.webb@company.com",
    action: "Contract viewed",
    resource: "Enterprise License — Microsoft 365",
    status: "success",
    ip: "10.0.2.18",
  },
  {
    id: "a005",
    timestamp: "2024-01-09 09:14:33",
    user: "Priya Nair",
    userEmail: "p.nair@company.com",
    action: "Comparison performed",
    resource: "Salesforce MSA vs. Microsoft Enterprise License",
    status: "success",
    ip: "10.0.1.87",
  },
  {
    id: "a006",
    timestamp: "2024-01-08 17:03:59",
    user: "James O'Brien",
    userEmail: "j.obrien@company.com",
    action: "Login",
    resource: "Authentication",
    status: "failed",
    ip: "192.168.1.14",
  },
  {
    id: "a007",
    timestamp: "2024-01-08 17:05:12",
    user: "James O'Brien",
    userEmail: "j.obrien@company.com",
    action: "Login",
    resource: "Authentication",
    status: "success",
    ip: "192.168.1.14",
  },
  {
    id: "a008",
    timestamp: "2024-01-08 13:27:00",
    user: "Sarah Chen",
    userEmail: "s.chen@company.com",
    action: "Contract uploaded",
    resource: "Master Services Agreement — Salesforce",
    status: "success",
    ip: "10.0.1.42",
  },
  {
    id: "a009",
    timestamp: "2024-01-07 10:45:23",
    user: "Admin",
    userEmail: "admin@company.com",
    action: "Permission change",
    resource: "Marcus Webb — Role updated to Manager",
    status: "success",
    ip: "10.0.0.1",
  },
  {
    id: "a010",
    timestamp: "2024-01-05 15:30:01",
    user: "Priya Nair",
    userEmail: "p.nair@company.com",
    action: "Contract deleted",
    resource: "Vendor Agreement — Obsolete",
    status: "success",
    ip: "10.0.1.87",
  },
];
