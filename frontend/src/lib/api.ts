export class ApiError extends Error {}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let r: Response;
  try {
    r = await fetch(`/api${path}`, init);
  } catch {
    throw new ApiError("We can't reach the server. Check your connection and try again.");
  }
  if (!r.ok) {
    let msg = `Something went wrong (${r.status}).`;
    try {
      const j = await r.json();
      if (typeof j.detail === "string") msg = j.detail;
    } catch {}
    throw new ApiError(msg);
  }
  return r.json();
}
const json = (method: string, body?: unknown): RequestInit => ({
  method, headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body),
});

import type { AdvisorReply, KycResult, Lang, Order, Quote } from "./types";

export const api = {
  advisor: (message: string, language: Lang, session_id?: string) =>
    call<AdvisorReply>("/advisor/message", json("POST", { message, language, session_id: session_id ?? null })),
  patchAddon: (qid: string, product_id: string, included: boolean) =>
    call<Quote>(`/quote/${qid}/addons`, json("PATCH", { product_id, included })),
  consentNotice: () => call<{ purpose: string; data_used: string[]; retention: string; withdraw: string }>("/kyc/consent"),
  consent: () => call<{ kyc_session_id: string; retention_hours: number }>("/kyc/consent", json("POST", { accepted: true })),
  upload: (sid: string, doc: string, file: Blob, name: string) => {
    const f = new FormData();
    f.append("file", file, name);
    return call<{ uploaded: string[]; missing: string[] }>(`/kyc/${sid}/upload/${doc}`, { method: "POST", body: f });
  },
  validate: (sid: string, udyam_waived = false) => call<KycResult>(`/kyc/${sid}/validate`, json("POST", { udyam_waived })),
  withdraw: (sid: string) => call<{ deleted: boolean }>(`/kyc/${sid}`, { method: "DELETE" }),
  applyKyc: (qid: string, sid: string) => call<Quote>(`/quote/${qid}/apply-kyc`, json("POST", { kyc_session_id: sid })),
  samples: () => call<{ id: string; label: string; expected: string }[]>("/demo/kyc-samples"),
  sampleDoc: async (kid: string, doc: string): Promise<Blob | null> => {
    const r = await fetch(`/api/demo/kyc-samples/${kid}/${doc}`);
    return r.ok ? r.blob() : null;
  },
  createOrder: (quote_id: string, kyc_session_id: string, language: Lang, contact_phone?: string) =>
    call<Order>("/orders", json("POST", { quote_id, kyc_session_id, language, contact_phone: contact_phone || null })),
  esign: (oid: string, signatory_name: string, otp: string) => call<Order>(`/orders/${oid}/esign`, json("POST", { signatory_name, otp })),
  pay: (oid: string, method: string, simulate_failure: boolean) => call<Order>(`/orders/${oid}/pay`, json("POST", { method, simulate_failure })),
  advance: (oid: string) => call<Order>(`/orders/${oid}/advance`, json("POST")),
};
