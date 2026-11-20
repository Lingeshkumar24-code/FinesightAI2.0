import { useEffect, useState, type ChangeEvent } from "react";
import { api, ApiError, type ExtractedField, type VerificationDocument } from "../lib/api";
import { Card } from "../components/ui/Card";

export function DocumentVerification() {
  const [documents, setDocuments] = useState<VerificationDocument[]>([]);
  const [selected, setSelected] = useState<VerificationDocument | null>(null);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      setDocuments(await api.listVerificationDocuments());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load documents");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const document = await api.verifyDocument(file);
      setSelected(document);
      setEdits(Object.fromEntries(document.fields.map((field) => [field.id, field.field_value])));
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not verify document");
    } finally {
      setBusy(false);
    }
  }

  async function choose(documentId: string) {
    try {
      setSelected(await api.getVerificationDocument(documentId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load document");
    }
  }

  async function verifyField(field: ExtractedField) {
    setBusy(true);
    setError(null);
    try {
      const updated = await api.verifyExtractedField(field.id, {
        verified: true,
        field_value: edits[field.id] ?? field.field_value,
      });
      setSelected((current) => current ? {
        ...current,
        fields: current.fields.map((item) => item.id === updated.id ? updated : item),
      } : current);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not verify field");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-enter flex flex-col gap-5 w-full" data-testid="verification-page">
      <div className="page-header">
        <div>
          <h1>Document Verification</h1>
          <p className="page-lead">Extract financial and invoice fields, cross-check stored figures, and confirm values manually.</p>
        </div>
        <span className="data-badge is-demo">confidence-scored</span>
      </div>

      {error && <div className="page-state is-error"><p className="error-text">{error}</p></div>}

      <div className="split-grid">
        <Card>
          <div className="section-header"><h2>Verify Document</h2><span className="section-run">txt · csv · md · xlsx · pdf</span></div>
          <input aria-label="Document file" type="file" accept=".txt,.csv,.md,.xlsx,.pdf" onChange={(e) => void upload(e)} disabled={busy} />
          {selected && (
            <div className="stat-strip mt-4">
              <div><span>File</span><strong>{selected.filename}</strong></div>
              <div><span>Chunks Indexed</span><strong className="num">{selected.chunks}</strong></div>
              <div><span>Fields</span><strong className="num">{selected.fields.length}</strong></div>
            </div>
          )}
        </Card>

        <Card>
          <div className="section-header"><h2>Document Library</h2><span className="section-run">{documents.length} documents</span></div>
          <div className="portfolio-list" style={{ maxHeight: 420, overflowY: "auto" }}>
            {documents.map((document) => (
              <button
                key={document.id}
                type="button"
                className={`portfolio-row ${selected?.id === document.id ? "is-active" : ""}`}
                onClick={() => void choose(document.id)}
              >
                <span>{document.filename}</span>
                <small>{document.fields.length} fields</small>
                <small>{document.status}</small>
              </button>
            ))}
            {documents.length === 0 && <p className="muted-note">No documents verified yet.</p>}
          </div>
        </Card>
      </div>

      <Card>
        <div className="section-header"><h2>Extracted Fields</h2><span className="section-run">manual confirmation required unless cross-checked</span></div>
        <div className="data-table">
          <table>
            <thead><tr><th>Field</th><th>Value</th><th className="num">Confidence</th><th>Period</th><th>Status</th><th>Action</th></tr></thead>
            <tbody>
              {(selected?.fields ?? []).map((field) => (
                <tr key={field.id}>
                  <td>{field.field_name.replace(/_/g, " ")}</td>
                  <td>
                    <input
                      aria-label={`${field.field_name.replace(/_/g, " ")} value`}
                      value={edits[field.id] ?? field.field_value}
                      onChange={(e) => setEdits({ ...edits, [field.id]: e.target.value })}
                    />
                  </td>
                  <td className="num">{(field.confidence * 100).toFixed(0)}%</td>
                  <td>{field.period || "—"}</td>
                  <td><span className={`pill ${field.verified ? "is-good" : "is-bad"}`}>{field.verified ? "verified" : "unconfirmed"}</span></td>
                  <td>
                    <button type="button" className="btn btn-primary btn-small" disabled={busy || field.verified} onClick={() => void verifyField(field)}>
                      Confirm
                    </button>
                  </td>
                </tr>
              ))}
              {!selected && <tr><td colSpan={6} className="muted-note">Upload or select a document to inspect fields.</td></tr>}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
