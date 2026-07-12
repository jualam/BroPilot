"use client";

import type { ChangeEvent, ReactNode } from "react";
import { useMemo, useState } from "react";
import Link from "next/link";

const OPS_API_URL = "http://127.0.0.1:8000/api/ops-pilot/generate";
const OPS_EXTRACT_API_URL = "http://127.0.0.1:8000/api/ops-pilot/extract";

const defaultNotes = `Average customer onboarding time is 21 days.
Support backlog increased 34% over the last quarter.
Enterprise customers are delayed by security questionnaires and procurement reviews.
Account setup is mostly manual and handled by customer success.
Implementation managers answer the same onboarding questions repeatedly.
Customers often become inactive if they do not complete activation by week 2.
Regional health groups have higher ACV but slower procurement.
Customer success wants alerts for accounts stuck in onboarding.
Leadership wants automation opportunities that can be tested within 30 days.
Current tools include Salesforce, Zendesk, Google Sheets, Slack, and email.
Main goal: reduce onboarding time, lower support backlog, and improve activation.`;

const workflowOptions = [
  "Customer onboarding and support operations",
  "Sales operations",
  "Customer success operations",
  "Implementation / delivery operations",
  "Finance / reporting operations",
  "Recruiting / people operations",
  "General operations",
];

type Stage = {
  name: string;
  status: string;
  summary: string;
};

type Signal = {
  type: string;
  evidence: string;
  source: string;
  confidence: string;
};

type ExtractedTable = {
  title: string;
  markdown: string;
  rows?: Record<string, string>[];
};

type PdfDocument = {
  filename: string;
  document_type: string;
  extraction_status: string;
  summary: string;
  tables?: ExtractedTable[];
};

type OpsReview = {
  summary: string;
  operational_bottlenecks: {
    title: string;
    evidence: string;
    root_cause: string;
    source: string;
  }[];
  automation_opportunities: {
    title: string;
    workflow: string;
    why_it_matters: string;
    suggested_automation: string;
    source: string;
  }[];
  priority_ranking: {
    opportunity: string;
    impact: string;
    effort: string;
    confidence: string;
    reason: string;
  }[];
  recommended_first_workflow: {
    title: string;
    why_first: string;
    scope: string;
    human_owner: string;
  };
  thirty_day_plan: {
    week: string;
    goal: string;
    actions: string[];
  }[];
  metrics_to_track: {
    metric: string;
    why_it_matters: string;
    baseline_or_target: string;
  }[];
  risks_and_assumptions: string[];
  questions_for_operator: string[];
  reviewer_notes: string[];
};

type OpsResult = {
  company_name: string;
  workflow_area: string;
  ocr: {
    status: string;
    text: string;
    detail: string;
    image_filename: string;
    pdf_documents: PdfDocument[];
  };
  signals: Signal[];
  stages: Stage[];
  ops_review: OpsReview;
  artifact_markdown: string;
  generated_at: string;
  generation: {
    mode: string;
    model: string;
    fallback_reason: string;
  };
};

export default function OpsPilotPage() {
  const [companyName, setCompanyName] = useState("");
  const [workflowArea, setWorkflowArea] = useState("");
  const [manualNotes, setManualNotes] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [pdfFiles, setPdfFiles] = useState<File[]>([]);
  const [result, setResult] = useState<OpsResult | null>(null);
  const [extractionPreview, setExtractionPreview] = useState<OpsResult["ocr"] | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [ocrDetails, setOcrDetails] = useState<OpsResult["ocr"] | null>(null);

  const slug = useMemo(() => slugify(companyName || "company"), [companyName]);

  function handleImage(event: ChangeEvent<HTMLInputElement>) {
    setImageFile(event.target.files?.[0] ?? null);
    setExtractionPreview(null);
    event.target.value = "";
  }

  function handlePdfs(event: ChangeEvent<HTMLInputElement>) {
    const incoming = Array.from(event.target.files ?? []);
    setExtractionPreview(null);
    setPdfFiles((current) => {
      const byKey = new Map(current.map((file) => [`${file.name}-${file.size}-${file.lastModified}`, file]));
      incoming.forEach((file) => byKey.set(`${file.name}-${file.size}-${file.lastModified}`, file));
      return Array.from(byKey.values());
    });
    event.target.value = "";
  }

  async function generateOpsReview() {
    setIsLoading(true);
    setIsExtracting(true);
    setError(null);
    setCopied(false);
    setResult(null);
    setExtractionPreview(null);

    const buildFormData = () => {
      const formData = new FormData();
      if (imageFile) {
        formData.append("image", imageFile);
      }
      pdfFiles.forEach((file) => formData.append("pdfs", file));
      formData.append("manual_notes", manualNotes);
      formData.append("company_name", companyName);
      formData.append("workflow_area", workflowArea);
      return formData;
    };

    try {
      const extractionResponse = await fetch(OPS_EXTRACT_API_URL, {
        method: "POST",
        body: buildFormData(),
      });
      if (!extractionResponse.ok) {
        const payload = await extractionResponse.json().catch(() => null);
        throw new Error(payload?.detail ?? `Backend returned ${extractionResponse.status}`);
      }
      const extractionPayload = (await extractionResponse.json()) as { ocr?: OpsResult["ocr"] };
      setExtractionPreview(extractionPayload.ocr ?? null);
      setIsExtracting(false);

      const response = await fetch(OPS_API_URL, {
        method: "POST",
        body: buildFormData(),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Backend returned ${response.status}`);
      }
      setResult((await response.json()) as OpsResult);
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Ops Pilot could not generate the operations review.",
      );
    } finally {
      setIsLoading(false);
      setIsExtracting(false);
    }
  }

  async function copyMarkdown() {
    if (!result) {
      return;
    }
    await navigator.clipboard.writeText(result.artifact_markdown);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  function downloadMarkdown() {
    if (!result) {
      return;
    }
    downloadBlob(result.artifact_markdown, `${slug}_ops_review.md`, "text/markdown;charset=utf-8");
  }

  function downloadPdf() {
    if (!result) {
      return;
    }
    const popup = window.open("", "_blank", "width=900,height=1100");
    if (!popup) {
      setError("Browser blocked the PDF export window.");
      return;
    }
    popup.document.write(buildPrintableOpsReview(result));
    popup.document.close();
    popup.focus();
    popup.print();
  }

  return (
    <main className="min-h-screen bg-white text-zinc-950">
      <TopNav />
      <section className="mx-auto grid w-full max-w-7xl gap-8 px-5 pb-20 pt-10 sm:px-8 lg:px-10">
        <div className="grid gap-6 lg:grid-cols-[0.85fr_1.15fr] lg:items-end">
          <div>
            <h1 className="font-copperplate text-5xl font-semibold text-zinc-950 sm:text-6xl">
              Ops Pilot
            </h1>
            <p className="mt-4 max-w-2xl text-xl leading-8 text-zinc-600">
              Messy operating notes and screenshots to a review-ready operations improvement plan.
            </p>
          </div>
          <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-5 text-sm leading-6 text-zinc-600">
            Ops Pilot identifies bottlenecks, automation opportunities, risks, and a 30-day pilot plan for human review. It does not guarantee ROI or make final operating decisions.
          </div>
        </div>

        <section className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm">
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="grid min-w-0 gap-2">
                <span className="text-sm font-semibold text-zinc-800">Company name</span>
                <input
                  className="min-h-11 rounded-md border border-zinc-300 bg-white px-3 text-sm outline-none focus:border-zinc-950"
                  onChange={(event) => setCompanyName(event.target.value)}
                  placeholder="Company name"
                  value={companyName}
                />
              </label>
              <label className="grid min-w-0 gap-2">
                <span className="text-sm font-semibold text-zinc-800">Workflow area</span>
                <select
                  className="min-h-11 min-w-0 rounded-md border border-zinc-300 bg-white px-3 text-sm outline-none focus:border-zinc-950"
                  onChange={(event) => setWorkflowArea(event.target.value)}
                  value={workflowArea}
                >
                  <option value="">Select workflow area</option>
                  {workflowOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <UploadBox
                accept="image/png,image/jpeg,image/webp,image/bmp"
                buttonLabel={imageFile ? "Replace image" : "Upload image"}
                description="Screenshot, whiteboard, or operating notes."
                fileNames={imageFile ? [imageFile.name] : []}
                label="Image / OCR"
                onChange={handleImage}
                onClear={() => {
                  setImageFile(null);
                  setExtractionPreview(null);
                }}
              />
              <UploadBox
                accept="application/pdf"
                buttonLabel={pdfFiles.length ? "Add PDFs" : "Upload PDFs"}
                description="Optional support summaries or operating docs."
                fileNames={pdfFiles.map((file) => file.name)}
                label="Optional PDFs"
                multiple
                onChange={handlePdfs}
                onClear={() => {
                  setPdfFiles([]);
                  setExtractionPreview(null);
                }}
              />
            </div>

            <label className="mt-5 grid gap-2">
              <span className="flex flex-wrap items-center justify-between gap-3">
                <span className="text-sm font-semibold text-zinc-800">Manual notes</span>
                <button
                  className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-xs font-semibold text-zinc-700 shadow-sm transition hover:bg-zinc-100 hover:text-zinc-950"
                  onClick={() => {
                    setManualNotes(defaultNotes);
                    setExtractionPreview(null);
                  }}
                  type="button"
                >
                  Load sample data
                </button>
              </span>
              <textarea
                className="min-h-56 resize-y rounded-md border border-zinc-300 bg-white px-3 py-3 text-sm leading-6 outline-none focus:border-zinc-950"
                onChange={(event) => {
                  setManualNotes(event.target.value);
                  setExtractionPreview(null);
                }}
                placeholder="Paste operating notes, support summaries, onboarding issues, support backlog notes, or call notes..."
                value={manualNotes}
              />
            </label>

            <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center">
              <button
                className="inline-flex min-h-11 items-center justify-center rounded-md bg-zinc-950 px-5 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-400"
                disabled={isLoading}
                onClick={generateOpsReview}
                type="button"
              >
                {isLoading
                  ? isExtracting
                    ? "Extracting inputs..."
                    : "Generating Ops Review..."
                  : "Generate Ops Review"}
              </button>
              {error ? (
                <p className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                  {error}
                </p>
              ) : null}
            </div>
          </div>

          <section className="rounded-lg border border-zinc-200 bg-zinc-50 p-6 shadow-sm">
            <h2 className="text-xl font-semibold tracking-tight">Operating Inputs</h2>
            <div className="mt-4 grid gap-3">
              <InputStatus label="Image" value={imageFile?.name ?? "Not uploaded"} />
              <InputStatus
                label="PDFs"
                value={
                  pdfFiles.length
                    ? `${pdfFiles.length} PDF(s): ${pdfFiles.map((file) => file.name).join(", ")}`
                    : "Not uploaded"
                }
              />
              <InputStatus label="Manual notes" value={manualNotes.trim() ? "Ready" : "Not provided"} />
              {result?.ocr || extractionPreview ? (
                <>
                  <ImageOcrCard
                    ocr={result?.ocr ?? extractionPreview}
                    onViewDetails={(ocr) => setOcrDetails(ocr)}
                  />
                  <UploadedPdfDocuments
                    documents={(result?.ocr ?? extractionPreview)?.pdf_documents ?? []}
                    files={pdfFiles}
                    isExtracting={isExtracting}
                  />
                </>
              ) : isExtracting ? (
                <p className="rounded-md border border-zinc-200 bg-white p-5 text-sm leading-6 text-zinc-500">
                  Extracting OCR text and parsing PDFs...
                </p>
              ) : (
                <p className="rounded-md border border-dashed border-zinc-300 bg-white/70 p-5 text-sm leading-6 text-zinc-500">
                  OCR status, extracted text, and PDF parsing summaries will appear after generation.
                </p>
              )}
            </div>
          </section>
        </section>

        {ocrDetails ? (
          <ImageOcrModal
            ocr={ocrDetails}
            onClose={() => setOcrDetails(null)}
          />
        ) : null}

        {result ? (
          <>
            <section className="grid items-stretch gap-5 xl:grid-cols-[0.8fr_1.2fr]">
              <FlightRecorder stages={result.stages} />
              <SignalsPanel signals={result.signals} />
            </section>
            <OpsOutput result={result} />
            <ExportPanel
              copied={copied}
              onCopy={copyMarkdown}
              onDownloadMarkdown={downloadMarkdown}
              onDownloadPdf={downloadPdf}
              result={result}
            />
          </>
        ) : (
          <div className="rounded-lg border border-dashed border-zinc-300 bg-zinc-50 p-8 text-center text-sm text-zinc-500">
            Flight Recorder, signals, priority ranking, 30-day plan, and exports will appear after generation.
          </div>
        )}
      </section>
    </main>
  );
}

function TopNav() {
  return (
    <header className="sticky top-0 z-20 border-b border-zinc-200/80 bg-white/90 backdrop-blur">
      <nav className="mx-auto flex min-h-16 w-full max-w-7xl items-center justify-between gap-6 px-5 sm:px-8 lg:px-10">
        <Link
          aria-label="BroPilot Workbench home"
          className="relative block h-[46px] w-[224px] shrink-0 overflow-hidden"
          href="/"
        >
          <img
            alt="BroPilot Workbench"
            className="absolute -left-[52px] -top-[50px] h-auto w-[520px] max-w-none"
            src="/bropilot-workbench-logo.svg"
          />
        </Link>
        <div className="hidden items-center gap-1 text-sm text-zinc-600 md:flex">
          <Link className="rounded-md px-3 py-2 transition hover:bg-zinc-100 hover:text-zinc-950" href="/">
            Home
          </Link>
          <Link className="rounded-md px-3 py-2 transition hover:bg-zinc-100 hover:text-zinc-950" href="/code-pilot">
            Code Pilot
          </Link>
          <Link className="rounded-md px-3 py-2 transition hover:bg-zinc-100 hover:text-zinc-950" href="/memo-pilot">
            Memo Pilot
          </Link>
          <Link className="rounded-md bg-zinc-100 px-3 py-2 text-zinc-950 transition hover:bg-zinc-100" href="/ops-pilot">
            Ops Pilot
          </Link>
          <Link className="rounded-md px-3 py-2 transition hover:bg-zinc-100 hover:text-zinc-950" href="/architecture">
            Workflow Pattern
          </Link>
        </div>
      </nav>
    </header>
  );
}

function UploadBox({
  accept,
  buttonLabel,
  description,
  fileNames,
  label,
  multiple = false,
  onChange,
  onClear,
}: {
  accept: string;
  buttonLabel: string;
  description: string;
  fileNames: string[];
  label: string;
  multiple?: boolean;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onClear: () => void;
}) {
  return (
    <div className="rounded-md border border-dashed border-zinc-300 bg-zinc-50 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-zinc-800">{label}</p>
          <p className="mt-1 text-xs leading-5 text-zinc-500">{description}</p>
        </div>
        <label className="inline-flex min-h-9 cursor-pointer items-center rounded-md border border-zinc-300 bg-white px-3 text-xs font-semibold text-zinc-950 shadow-sm transition hover:bg-zinc-100">
          {buttonLabel}
          <input accept={accept} className="sr-only" multiple={multiple} onChange={onChange} type="file" />
        </label>
      </div>
      {fileNames.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {fileNames.map((fileName) => (
            <span
              className="inline-flex max-w-full min-w-0 rounded-full border border-zinc-200 bg-white px-2.5 py-1 text-xs font-medium text-zinc-600"
              key={fileName}
              title={fileName}
            >
              <span className="min-w-0 truncate overflow-hidden text-ellipsis whitespace-nowrap">
                {fileName}
              </span>
            </span>
          ))}
          <button className="shrink-0 rounded-full border border-zinc-200 bg-white px-2.5 py-1 text-xs font-semibold text-zinc-500 hover:text-zinc-950" onClick={onClear} type="button">
            Clear
          </button>
        </div>
      ) : null}
    </div>
  );
}

function InputStatus({ label, value }: { label: string; value: string }) {
  return (
    <article className="rounded-md border border-zinc-200 bg-white p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-zinc-500">{label}</p>
      <p className="mt-2 break-words text-sm font-medium leading-6 text-zinc-800">{value}</p>
    </article>
  );
}

function ImageOcrCard({
  ocr,
  onViewDetails,
}: {
  ocr: OpsResult["ocr"] | null;
  onViewDetails: (ocr: OpsResult["ocr"]) => void;
}) {
  if (!ocr) {
    return null;
  }

  return (
    <article className="rounded-md border border-zinc-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-zinc-950">Image OCR</p>
          <p className="mt-1 text-sm text-zinc-600">{ocr.status}</p>
        </div>
        <button
          className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-xs font-semibold text-zinc-700 transition hover:bg-zinc-100"
          onClick={() => onViewDetails(ocr)}
          type="button"
        >
          View OCR details
        </button>
      </div>
    </article>
  );
}

function ImageOcrModal({
  ocr,
  onClose,
}: {
  ocr: OpsResult["ocr"];
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-zinc-950/35 px-4 py-6 backdrop-blur-sm">
      <section className="flex max-h-[88vh] w-full max-w-4xl flex-col overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-2xl">
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-zinc-200 p-5">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-zinc-950">Image OCR details</p>
            <div className="mt-2 flex flex-wrap gap-2 text-xs text-zinc-600">
              <span className="rounded-full border border-zinc-200 bg-zinc-50 px-2.5 py-1 font-medium">
                {ocr.status}
              </span>
              {ocr.image_filename ? (
                <span className="rounded-full border border-zinc-200 bg-zinc-50 px-2.5 py-1 font-medium">
                  {ocr.image_filename}
                </span>
              ) : null}
            </div>
          </div>
          <button
            className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-100 hover:text-zinc-950"
            onClick={onClose}
            type="button"
          >
            Close
          </button>
        </div>
        <div className="grid gap-5 overflow-auto p-5">
          <div className="rounded-md border border-zinc-200 bg-zinc-50 p-4">
            <h3 className="text-sm font-semibold uppercase tracking-[0.08em] text-zinc-500">
              OCR summary
            </h3>
            <p className="mt-3 text-sm leading-6 text-zinc-700">{ocr.detail}</p>
          </div>
          <div className="rounded-md border border-zinc-200 bg-zinc-50 p-4">
            <h3 className="text-sm font-semibold uppercase tracking-[0.08em] text-zinc-500">
              Extracted OCR text
            </h3>
            <pre className="mt-3 max-h-[52vh] overflow-auto whitespace-pre-wrap rounded-md border border-zinc-200 bg-white p-4 font-mono text-xs leading-5 text-zinc-700">
              {ocr.text || "No OCR text extracted."}
            </pre>
          </div>
        </div>
      </section>
    </div>
  );
}

function UploadedPdfDocuments({
  documents,
  files,
  isExtracting,
}: {
  documents: PdfDocument[];
  files: File[];
  isExtracting: boolean;
}) {
  const [selectedDocument, setSelectedDocument] = useState<PdfDocument | null>(null);

  return (
    <>
      <article className="rounded-md border border-zinc-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-zinc-950">PDF extraction</h3>
        <div className="mt-3 grid gap-3">
          {documents.length ? (
            documents.map((document) => (
              <section className="rounded-md border border-zinc-200 bg-zinc-50 p-3" key={document.filename}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="break-all font-mono text-xs font-semibold text-zinc-950">{document.filename}</p>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-zinc-600">
                      <span className="rounded-full border border-zinc-200 bg-white px-2.5 py-1 font-medium">
                        {document.extraction_status}
                      </span>
                      <span className="rounded-full border border-zinc-200 bg-white px-2.5 py-1 font-medium">
                        {document.tables?.length ?? 0} table{(document.tables?.length ?? 0) === 1 ? "" : "s"} extracted
                      </span>
                    </div>
                  </div>
                  <button
                    className="shrink-0 rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-xs font-semibold text-zinc-700 transition hover:bg-zinc-100"
                    onClick={() => setSelectedDocument(document)}
                    type="button"
                  >
                    View PDF details
                  </button>
                </div>
                <p
                  className="mt-3 overflow-hidden text-sm leading-6 text-zinc-600"
                  style={{
                    display: "-webkit-box",
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical",
                  }}
                >
                  {document.summary}
                </p>
              </section>
            ))
          ) : isExtracting ? (
            <p className="rounded-md border border-dashed border-zinc-300 bg-zinc-50 p-3 text-sm text-zinc-500">
              Parsing uploaded PDFs...
            </p>
          ) : files.length ? (
            files.map((file) => (
              <p className="rounded-md border border-zinc-200 bg-zinc-50 p-3 font-mono text-xs text-zinc-600" key={file.name}>
                {file.name} is ready for extraction.
              </p>
            ))
          ) : (
            <p className="rounded-md border border-dashed border-zinc-300 bg-zinc-50 p-3 text-sm text-zinc-500">
              No PDFs uploaded.
            </p>
          )}
        </div>
      </article>
      {selectedDocument ? (
        <PdfExtractionModal
          document={selectedDocument}
          onClose={() => setSelectedDocument(null)}
        />
      ) : null}
    </>
  );
}

function PdfExtractionModal({
  document,
  onClose,
}: {
  document: PdfDocument;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-zinc-950/35 px-4 py-6 backdrop-blur-sm">
      <section className="flex max-h-[88vh] w-full max-w-5xl flex-col overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-2xl">
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-zinc-200 p-5">
          <div className="min-w-0">
            <p className="break-all font-mono text-sm font-semibold text-zinc-950">{document.filename}</p>
            <div className="mt-2 flex flex-wrap gap-2 text-xs text-zinc-600">
              <span className="rounded-full border border-zinc-200 bg-zinc-50 px-2.5 py-1 font-medium">
                {document.extraction_status}
              </span>
              <span className="rounded-full border border-zinc-200 bg-zinc-50 px-2.5 py-1 font-medium">
                {document.tables?.length ?? 0} table{(document.tables?.length ?? 0) === 1 ? "" : "s"} extracted
              </span>
            </div>
          </div>
          <button
            className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-100 hover:text-zinc-950"
            onClick={onClose}
            type="button"
          >
            Close
          </button>
        </div>
        <div className="grid gap-5 overflow-auto p-5">
          <div className="rounded-md border border-zinc-200 bg-zinc-50 p-4">
            <h3 className="text-sm font-semibold uppercase tracking-[0.08em] text-zinc-500">
              PDF extraction summary
            </h3>
            <p className="mt-3 text-sm leading-6 text-zinc-700">{document.summary}</p>
          </div>
          <div className="grid gap-3">
            <h3 className="text-sm font-semibold uppercase tracking-[0.08em] text-zinc-500">
              Structured tables
            </h3>
            {document.tables?.length ? (
              document.tables.map((table) => (
                <ExtractedTablePreview table={table} key={table.title} />
              ))
            ) : (
              <p className="rounded-md border border-dashed border-zinc-300 bg-zinc-50 p-4 text-sm text-zinc-500">
                No structured tables were extracted from this PDF.
              </p>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

function ExtractedTablePreview({ table }: { table: ExtractedTable }) {
  const rows = table.rows ?? [];
  const headers = rows.length ? Object.keys(rows[0]) : [];

  return (
    <div className="overflow-hidden rounded-md border border-zinc-200 bg-zinc-50">
      <div className="flex items-center justify-between gap-3 border-b border-zinc-200 px-3 py-2">
        <p className="text-xs font-semibold text-zinc-700">{table.title}</p>
        <span className="text-xs text-zinc-500">{rows.length} row(s)</span>
      </div>
      {rows.length && headers.length ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] border-collapse text-left text-xs">
            <thead className="bg-white text-zinc-500">
              <tr>
                {headers.map((header) => (
                  <th className="border-b border-zinc-200 px-3 py-2 font-semibold" key={header}>
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 8).map((row, rowIndex) => (
                <tr className="align-top" key={`${table.title}-${rowIndex}`}>
                  {headers.map((header) => (
                    <td className="border-b border-zinc-100 px-3 py-2 text-zinc-700" key={header}>
                      {row[header]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <pre className="max-h-48 overflow-auto whitespace-pre-wrap p-3 font-mono text-xs leading-5 text-zinc-600">
          {table.markdown}
        </pre>
      )}
    </div>
  );
}

function FlightRecorder({ stages }: { stages: Stage[] }) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm">
      <h2 className="text-xl font-semibold tracking-tight">Flight Recorder</h2>
      <ol className="mt-5 grid gap-3">
        {stages.map((stage, index) => (
          <li className="grid grid-cols-[36px_minmax(0,1fr)] gap-4" key={stage.name}>
            <span className="grid size-9 place-items-center rounded-md bg-zinc-950 text-sm font-semibold text-white">
              {index + 1}
            </span>
            <article className="rounded-md border border-zinc-200 bg-zinc-50 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h3 className="font-semibold text-zinc-950">{stage.name}</h3>
                <span className="text-xs font-semibold text-emerald-700">{stage.status}</span>
              </div>
              <p className="mt-2 text-sm leading-6 text-zinc-600">{stage.summary}</p>
            </article>
          </li>
        ))}
      </ol>
    </section>
  );
}

function SignalsPanel({ signals }: { signals: Signal[] }) {
  return (
    <section className="flex h-full min-h-0 flex-col rounded-lg border border-zinc-200 bg-white p-6 shadow-sm">
      <h2 className="text-xl font-semibold tracking-tight">Operational Signals</h2>
      <div className="mt-5 grid min-h-0 flex-1 gap-2 overflow-auto pr-2">
        {signals.map((signal) => (
          <article className="rounded-md border border-zinc-200 bg-zinc-50 p-3" key={`${signal.type}-${signal.evidence}`}>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-sm font-semibold text-zinc-950">{signal.type}</h3>
              <span className="rounded-full border border-zinc-200 bg-white px-2 py-0.5 text-xs text-zinc-600">{signal.confidence}</span>
              <span className="rounded-full border border-zinc-200 bg-white px-2 py-0.5 text-xs text-zinc-600">{signal.source}</span>
            </div>
            <p className="mt-2 text-sm leading-5 text-zinc-600">{signal.evidence}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function OpsOutput({ result }: { result: OpsResult }) {
  const review = result.ops_review;
  const isLlm = result.generation.mode === "llm_grounded";
  return (
    <section className="grid gap-5">
      <article className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm">
        <div className="grid gap-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <h2 className="text-xl font-semibold tracking-tight">Executive Summary</h2>
            <span className="rounded-full border border-zinc-200 bg-zinc-50 px-3 py-1 text-xs font-semibold text-zinc-600">
              {isLlm ? `LLM: ${result.generation.model}` : "Deterministic fallback"}
            </span>
          </div>
          <p className="max-w-5xl text-sm leading-6 text-zinc-700">{review.summary}</p>
        </div>
        {result.generation.fallback_reason ? (
          <p className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            {result.generation.fallback_reason}
          </p>
        ) : null}
      </article>

      <RecommendedWorkflow workflow={review.recommended_first_workflow} />

      <section className="grid gap-5 xl:grid-cols-2">
        <CardList
          items={review.operational_bottlenecks}
          render={(item) => (
            <>
              <h3 className="font-semibold text-zinc-950">{item.title}</h3>
              <p className="mt-2 text-sm leading-6 text-zinc-600">{item.evidence}</p>
              <p className="mt-2 text-sm leading-6 text-zinc-700"><span className="font-semibold">Root cause:</span> {item.root_cause}</p>
            </>
          )}
          title="Operational Bottlenecks"
        />
        <CardList
          items={review.automation_opportunities}
          render={(item) => (
            <>
              <h3 className="font-semibold text-zinc-950">{item.title}</h3>
              <p className="mt-2 text-sm leading-6 text-zinc-600">{item.why_it_matters}</p>
              <p className="mt-2 text-sm leading-6 text-zinc-700"><span className="font-semibold">Automation:</span> {item.suggested_automation}</p>
            </>
          )}
          title="Automation Opportunities"
        />
      </section>

      <PriorityTable rows={review.priority_ranking} />

      <section className="grid gap-5 xl:grid-cols-2">
        <PlanCard plan={review.thirty_day_plan} />
        <MetricsCard metrics={review.metrics_to_track} />
      </section>

      <section className="grid gap-5 xl:grid-cols-3">
        <ListCard items={review.risks_and_assumptions} title="Risks and Assumptions" />
        <ListCard items={review.questions_for_operator} title="Questions for Operator" />
        <ListCard items={review.reviewer_notes} title="Reviewer Notes" />
      </section>
    </section>
  );
}

function RecommendedWorkflow({ workflow }: { workflow: OpsReview["recommended_first_workflow"] }) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-zinc-500">Recommended first workflow</p>
      <h2 className="mt-3 text-2xl font-semibold tracking-tight text-zinc-950">{workflow.title}</h2>
      <p className="mt-3 max-w-4xl text-sm leading-6 text-zinc-700">{workflow.why_first}</p>
      <div className="mt-5 grid gap-3 md:grid-cols-2">
        <p className="rounded-md border border-zinc-200 bg-zinc-50 p-4 text-sm leading-6 text-zinc-700"><span className="font-semibold text-zinc-950">Scope:</span> {workflow.scope}</p>
        <p className="rounded-md border border-zinc-200 bg-zinc-50 p-4 text-sm leading-6 text-zinc-700"><span className="font-semibold text-zinc-950">Human owner:</span> {workflow.human_owner}</p>
      </div>
    </section>
  );
}

function CardList<T>({ items, render, title }: { items: T[]; render: (item: T) => ReactNode; title: string }) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm">
      <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
      <div className="mt-5 grid gap-3">
        {items.map((item, index) => (
          <article className="rounded-md border border-zinc-200 bg-zinc-50 p-4" key={index}>
            {render(item)}
          </article>
        ))}
      </div>
    </section>
  );
}

function PriorityTable({ rows }: { rows: OpsReview["priority_ranking"] }) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm">
      <h2 className="text-xl font-semibold tracking-tight">Priority Ranking</h2>
      <div className="mt-5 overflow-auto rounded-md border border-zinc-200">
        <table className="w-full min-w-[760px] border-collapse text-left text-sm">
          <thead className="bg-zinc-50 text-xs uppercase tracking-[0.08em] text-zinc-500">
            <tr>
              <th className="px-4 py-3">Opportunity</th>
              <th className="px-4 py-3">Impact</th>
              <th className="px-4 py-3">Effort</th>
              <th className="px-4 py-3">Confidence</th>
              <th className="px-4 py-3">Reason</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr className="border-t border-zinc-200 align-top" key={row.opportunity}>
                <td className="px-4 py-4 font-semibold text-zinc-950">{row.opportunity}</td>
                <td className="px-4 py-4">{row.impact}</td>
                <td className="px-4 py-4">{row.effort}</td>
                <td className="px-4 py-4">{row.confidence}</td>
                <td className="px-4 py-4 leading-6 text-zinc-600">{row.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function PlanCard({ plan }: { plan: OpsReview["thirty_day_plan"] }) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm">
      <h2 className="text-xl font-semibold tracking-tight">30-Day Action Plan</h2>
      <div className="mt-5 grid gap-3">
        {plan.map((week) => (
          <article className="rounded-md border border-zinc-200 bg-zinc-50 p-4" key={week.week}>
            <h3 className="font-semibold text-zinc-950">{week.week}: {week.goal}</h3>
            <ul className="mt-3 grid gap-2 text-sm leading-6 text-zinc-600">
              {week.actions.map((action) => (
                <li className="grid grid-cols-[8px_minmax(0,1fr)] gap-3" key={action}>
                  <span className="mt-2 size-1.5 rounded-full bg-zinc-950" />
                  <span>{action}</span>
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </section>
  );
}

function MetricsCard({ metrics }: { metrics: OpsReview["metrics_to_track"] }) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm">
      <h2 className="text-xl font-semibold tracking-tight">Metrics to Track</h2>
      <div className="mt-5 grid gap-3">
        {metrics.map((metric) => (
          <article className="rounded-md border border-zinc-200 bg-zinc-50 p-4" key={metric.metric}>
            <h3 className="font-semibold text-zinc-950">{metric.metric}</h3>
            <p className="mt-2 text-sm leading-6 text-zinc-600">{metric.why_it_matters}</p>
            <p className="mt-2 text-sm leading-6 text-zinc-700"><span className="font-semibold">Baseline/target:</span> {metric.baseline_or_target}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function ListCard({ items, title }: { items: string[]; title: string }) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm">
      <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
      <ul className="mt-5 grid gap-2 text-sm leading-6 text-zinc-700">
        {items.map((item) => (
          <li className="grid grid-cols-[8px_minmax(0,1fr)] gap-3" key={item}>
            <span className="mt-2 size-1.5 rounded-full bg-zinc-950" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ExportPanel({
  copied,
  onCopy,
  onDownloadMarkdown,
  onDownloadPdf,
  result,
}: {
  copied: boolean;
  onCopy: () => void;
  onDownloadMarkdown: () => void;
  onDownloadPdf: () => void;
  result: OpsResult;
}) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-zinc-50 p-6 shadow-sm">
      <h2 className="text-xl font-semibold tracking-tight">Copy-ready Markdown Artifact</h2>
      <p className="mt-2 text-sm leading-6 text-zinc-600">
        Prepared for human review, with signals retained as the audit trail.
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <button className="rounded-md bg-zinc-950 px-4 py-2 text-sm font-semibold text-white" onClick={onCopy} type="button">
          {copied ? "Copied" : "Copy Markdown"}
        </button>
        <button className="rounded-md border border-zinc-300 bg-white px-4 py-2 text-sm font-semibold text-zinc-950" onClick={onDownloadMarkdown} type="button">
          Download Markdown
        </button>
        <button className="rounded-md border border-zinc-300 bg-white px-4 py-2 text-sm font-semibold text-zinc-950" onClick={onDownloadPdf} type="button">
          Download PDF
        </button>
      </div>
      <pre className="mt-5 max-h-[520px] overflow-auto whitespace-pre-wrap rounded-md border border-zinc-200 bg-white p-4 font-mono text-xs leading-5 text-zinc-700">
        {result.artifact_markdown}
      </pre>
    </section>
  );
}

function downloadBlob(contents: string, filename: string, type: string) {
  const blob = new Blob([contents], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function buildPrintableOpsReview(result: OpsResult) {
  const safeMarkdown = result.artifact_markdown
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return `<!doctype html><html><head><title>${result.company_name} Ops Review</title><style>
body{font-family:Inter,Arial,sans-serif;color:#111;background:#fff;margin:40px;line-height:1.55}
h1,h2{border-bottom:1px solid #ddd;padding-bottom:8px} pre{white-space:pre-wrap;font-family:inherit}
.meta{color:#555;font-size:13px;margin-bottom:24px}
</style></head><body><h1>${result.company_name} Ops Review</h1><div class="meta">Generated ${new Date(result.generated_at).toLocaleDateString()} · Workflow: ${result.workflow_area}</div><pre>${safeMarkdown}</pre></body></html>`;
}

function slugify(value: string) {
  return value.trim().replace(/[^a-z0-9]+/gi, "_").replace(/^_+|_+$/g, "") || "company";
}
