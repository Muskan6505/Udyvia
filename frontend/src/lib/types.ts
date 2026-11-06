export type Lang = "en" | "hi";
export type Step = "welcome" | "advisor" | "quote" | "consent" | "kyc" | "sign" | "track";

export interface Slots {
  business_type: string | null; employees: number | null; sites: number | null; city: string | null;
  has_gstin: boolean | null; gstin: string | null; current_internet: string | null;
  needs: string[]; budget_monthly: number | null; asked_needs: boolean;
}
export interface QuoteLine {
  product_id: string; product_name: string; unit: string; qty: number; unit_price: number;
  line_monthly: number; line_setup: number; included: boolean; role: string; reason: string;
}
export interface Blocked { product_id: string; product_name: string; reasons: string[]; alternative: string | null; upgrade_path: string }
export interface Quote {
  quote_id: string; segment: string; profile: { business_type: string; employees: number; sites: number; city: string; city_tier: number };
  gstin_status: string; lines: QuoteLine[]; monthly_total: number; setup_total: number; contract_months: number;
  expected_install_days: number; within_budget: boolean | null; blocked: Blocked[]; notes: string[]; kyc_decision: string | null;
}
export interface AdvisorReply { session_id: string; reply: string; slots: Slots; missing: string[]; ready: boolean; source: string; quote: Quote | null; quote_id?: string }
export interface Finding { code: string; severity: "fix" | "review" | "restrict" | "info"; doc: string | null; message: string }
export interface KycResult { decision: "PASS" | "NEEDS_FIX" | "MANUAL_REVIEW" | "RESTRICTED"; findings: Finding[]; gst_products_allowed: boolean; verified: Record<string, any>; autofill: Record<string, string> }
export interface TimelineStep { code: string; label: string; state: "done" | "current" | "upcoming" | "failed"; done_on: string | null; expected_on: string }
export interface Notification { date: string; channel: string; to: string | null; template: string; text: string }
export interface Order {
  order_id: string; status: string; as_of: string; next_action: string; expected_activation: string; days_to_activation: number;
  steps: TimelineStep[]; items: { product_id: string; name: string; qty: number; expected_live_on: string }[];
  notifications: Notification[]; amount_due: number; monthly_total: number; setup_total: number; contract_months: number;
  payment: { attempts: number; last_result: string | null; method: string | null }; help?: string;
}
export const DOC_TYPES = ["gst_certificate", "udyam_certificate", "signatory_id", "address_proof"] as const;
export type DocType = (typeof DOC_TYPES)[number];
