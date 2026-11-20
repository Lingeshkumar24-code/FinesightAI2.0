import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  api,
  type FraudAlert,
  type FraudSummary,
  type FraudTransaction,
  type FraudUpload,
  type ExtractedField,
  type VerificationDocument,
} from "../lib/api";
import { FraudDetection } from "../pages/FraudDetection";
import { DocumentVerification } from "../pages/DocumentVerification";

const alert: FraudAlert = {
  id: "alert-1", transaction_id: "FR-001", amount: -250000, date: "2026-11-01", vendor: "Acme Corp",
  risk_level: "high", reason: "Duplicate identifier", detection_method: "duplicate_identifier",
  recommended_action: "Hold payment", status: "open", created_at: "2026-11-19T00:00:00Z",
};

const summary: FraudSummary = {
  total_transactions: 3, suspicious_transactions: 1, high_risk_alerts: 1, duplicate_count: 1,
  risk_distribution: { high: 1 }, status_distribution: { open: 1 }, alerts: [alert], review_history: [],
};

const transaction: FraudTransaction = {
  id: "tx-fraud-1", business_id: "demo-business-001", transaction_id: "FR-001", date: "2026-11-01",
  amount: -250000, vendor: "Acme Corp", transaction_type: "payment", reference: "INV-900",
  source: "upload", batch_id: "batch-1", created_at: "2026-11-19T00:00:00Z",
};

const uploadResult: FraudUpload = {
  batch_id: "batch-2", received: 1, valid: 1, invalid: 0, validation_errors: [], alerts_created: 1,
  summary,
};

const field: ExtractedField = {
  id: "field-1", document_id: "doc-1", field_name: "total_amount", field_value: "45000",
  confidence: 0.94, verified: false, period: "2026-Q3",
};

const document: VerificationDocument = {
  id: "doc-1", filename: "invoice.txt", status: "processed", created_at: "2026-11-19T00:00:00Z",
  chunks: 2, fields: [field],
};

function mockFraudApis() {
  vi.spyOn(api, "getFraudSummary").mockResolvedValue(summary);
  vi.spyOn(api, "listFraudAlerts").mockResolvedValue([alert]);
  vi.spyOn(api, "listFraudTransactions").mockResolvedValue([transaction]);
}

describe("Phase 4 trust pages", () => {
  it("renders fraud alerts and submits a review", async () => {
    mockFraudApis();
    const review = vi.spyOn(api, "reviewFraudAlert").mockResolvedValue({ ...alert, status: "confirmed" });

    render(<FraudDetection />);
    expect(await screen.findByTestId("fraud-page")).toBeInTheDocument();
    expect(screen.getAllByText("FR-001").length).toBeGreaterThan(0);
    expect(screen.getByText("high")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(review).toHaveBeenCalledWith("alert-1", expect.objectContaining({ action: "confirm" })));
    vi.restoreAllMocks();
  });

  it("uploads a fraud CSV", async () => {
    mockFraudApis();
    const upload = vi.spyOn(api, "uploadFraudTransactions").mockResolvedValue(uploadResult);

    render(<FraudDetection />);
    expect(await screen.findByTestId("fraud-page")).toBeInTheDocument();
    const file = new File(["transaction_id,date,amount,vendor\nFR-9,2026-11-19,-100,Shop"], "fraud.csv", { type: "text/csv" });
    fireEvent.change(screen.getByLabelText("Fraud transaction CSV"), { target: { files: [file] } });
    await waitFor(() => expect(upload).toHaveBeenCalledWith(file));
    expect(await screen.findByText(/1 alerts from 1 valid rows/)).toBeInTheDocument();
    vi.restoreAllMocks();
  });

  it("renders document fields and confirms an extracted value", async () => {
    vi.spyOn(api, "listVerificationDocuments").mockResolvedValue([document]);
    vi.spyOn(api, "getVerificationDocument").mockResolvedValue(document);
    const verifyField = vi.spyOn(api, "verifyExtractedField").mockResolvedValue({ ...field, verified: true });

    render(<DocumentVerification />);
    expect(await screen.findByTestId("verification-page")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /invoice.txt/ }));
    expect(await screen.findByLabelText("total amount value")).toHaveValue("45000");

    fireEvent.change(screen.getByLabelText("total amount value"), { target: { value: "45000.00" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(verifyField).toHaveBeenCalledWith("field-1", { verified: true, field_value: "45000.00" }));
    vi.restoreAllMocks();
  });
});
