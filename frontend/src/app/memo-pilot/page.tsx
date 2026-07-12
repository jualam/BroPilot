"use client";

import type { ChangeEvent } from "react";
import { useMemo, useState } from "react";
import Link from "next/link";

const MEMO_API_URL = "http://127.0.0.1:8000/api/memo-pilot/generate";

type DocumentResult = {
  filename: string;
  document_type: string;
  extraction_status: string;
  summary: string;
  tables?: ExtractedTable[];
};

type EvidenceItem = {
  fact: string;
  source_document: string;
  category: string;
  support_level: string;
  evidence_type?: string;
  table_title?: string;
};

type ExtractedTable = {
  title: string;
  markdown: string;
  rows?: Record<string, string>[];
};

type Stage = {
  name: string;
  status: string;
  summary: string;
};

type MemoResult = {
  documents: DocumentResult[];
  evidence: EvidenceItem[];
  stages: Stage[];
  memo: {
    executive_summary: string;
    company_overview: string;
    product_value_proposition: string;
    market_customer_thesis: string;
    traction_financial_signals: string;
    gtm_motion: string;
    competitive_landscape: string;
    key_risks: string[];
    missing_evidence: string[];
    diligence_questions: string[];
    reviewer_notes: string[];
  };
  charts: {
    arr_growth: { year: string; arr: number; display_value?: string }[];
    evidence_completeness: { category: string; score: number }[];
    risk_priority: { risk: string; score: number; reason?: string; source?: string }[];
  };
  artifact_markdown: string;
  generated_at: string;
  memo_generation?: {
    mode: string;
    model: string;
    fallback_reason: string;
  };
};

const memoSections = [
  ["Executive Summary", "executive_summary"],
  ["Company Overview", "company_overview"],
  ["Product / Value Proposition", "product_value_proposition"],
  ["Market and Customer Thesis", "market_customer_thesis"],
  ["Traction and Financial Signals", "traction_financial_signals"],
  ["Go-to-Market Motion", "gtm_motion"],
  ["Competitive Landscape", "competitive_landscape"],
] as const;

const marketCategories = [
  "Fintech",
  "Healthcare",
  "Vertical SaaS",
  "AI infrastructure",
  "Cybersecurity",
  "Industrial software",
  "Consumer",
  "Other",
];

export default function MemoPilotPage() {
  const [companyName, setCompanyName] = useState("");
  const [marketCategory, setMarketCategory] = useState("");
  const [otherMarketCategory, setOtherMarketCategory] = useState("");
  const [manualNotes, setManualNotes] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [result, setResult] = useState<MemoResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const companySlug = useMemo(
    () => slugify(companyName || "company"),
    [companyName],
  );
  const selectedMarketCategory =
    marketCategory === "Other"
      ? otherMarketCategory.trim()
      : marketCategory;

  function handleFiles(event: ChangeEvent<HTMLInputElement>) {
    const incomingFiles = Array.from(event.target.files ?? []);
    setFiles((currentFiles) => {
      const byKey = new Map(
        currentFiles.map((file) => [`${file.name}-${file.size}-${file.lastModified}`, file]),
      );
      incomingFiles.forEach((file) => {
        byKey.set(`${file.name}-${file.size}-${file.lastModified}`, file);
      });
      return Array.from(byKey.values());
    });
    event.target.value = "";
  }

  function removeFile(fileToRemove: File) {
    setFiles((currentFiles) =>
      currentFiles.filter(
        (file) =>
          `${file.name}-${file.size}-${file.lastModified}` !==
          `${fileToRemove.name}-${fileToRemove.size}-${fileToRemove.lastModified}`,
      ),
    );
  }

  async function generateMemo() {
    setIsLoading(true);
    setError(null);
    setCopied(false);

    const formData = new FormData();
    files.forEach((file) => formData.append("documents", file));
    formData.append("manual_notes", manualNotes);
    formData.append("company_name", companyName);
    formData.append("sector", selectedMarketCategory);

    try {
      const response = await fetch(MEMO_API_URL, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Backend returned ${response.status}`);
      }

      setResult((await response.json()) as MemoResult);
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Memo Pilot could not generate the memo.",
      );
    } finally {
      setIsLoading(false);
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
    downloadBlob(
      result.artifact_markdown,
      `${companySlug}_diligence_memo.md`,
      "text/markdown;charset=utf-8",
    );
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
    popup.document.write(buildPrintableMemo(result, companyName, selectedMarketCategory));
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
              Memo Pilot
            </h1>
            <p className="mt-4 max-w-2xl text-xl leading-8 text-zinc-600">
              Multiple company documents and notes to a review-ready diligence memo draft.
            </p>
          </div>
          <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-5 text-sm leading-6 text-zinc-600">
            Memo Pilot does not make an investment decision. It separates facts,
            assumptions, risks, missing evidence, and diligence questions for
            human review.
          </div>
        </div>

        <section className="grid gap-5 lg:grid-cols-[0.95fr_1.05fr]">
          <div className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm">
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="grid gap-2">
                <span className="text-sm font-semibold text-zinc-800">Company name</span>
                <input
                  className="min-h-11 rounded-md border border-zinc-300 bg-white px-3 text-sm outline-none focus:border-zinc-950"
                  onChange={(event) => setCompanyName(event.target.value)}
                  placeholder="ExampleCo"
                  value={companyName}
                />
              </label>
              <label className="grid gap-2">
                <span className="text-sm font-semibold text-zinc-800">Market / category</span>
                <select
                  className="min-h-11 rounded-md border border-zinc-300 bg-white px-3 text-sm outline-none focus:border-zinc-950"
                  onChange={(event) => setMarketCategory(event.target.value)}
                  value={marketCategory}
                >
                  <option value="">Select category</option>
                  {marketCategories.map((category) => (
                    <option key={category} value={category}>
                      {category}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {marketCategory === "Other" ? (
              <label className="mt-4 grid gap-2">
                <span className="text-sm font-semibold text-zinc-800">Other category</span>
                <input
                  className="min-h-11 rounded-md border border-zinc-300 bg-white px-3 text-sm outline-none focus:border-zinc-950"
                  onChange={(event) => setOtherMarketCategory(event.target.value)}
                  placeholder="Example: Climate software"
                  value={otherMarketCategory}
                />
              </label>
            ) : null}

            <label className="mt-5 grid gap-2">
              <span className="text-sm font-semibold text-zinc-800">Company PDFs</span>
              <div className="rounded-md border border-dashed border-zinc-300 bg-zinc-50 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-zinc-800">Company document upload</p>
                    <p className="mt-1 text-xs text-zinc-500">
                      Add one or more PDFs before generating the memo.
                    </p>
                  </div>
                  <span className="inline-flex min-h-10 cursor-pointer items-center rounded-md border border-zinc-300 bg-white px-4 text-sm font-semibold text-zinc-950 shadow-sm transition hover:bg-zinc-100">
                    {files.length ? "Add more PDFs" : "Choose PDFs"}
                    <input
                      accept="application/pdf"
                      className="sr-only"
                      multiple
                      onChange={handleFiles}
                      type="file"
                    />
                  </span>
                </div>
                {files.length ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {files.map((file) => (
                      <span
                        className="inline-flex items-center gap-2 rounded-full border border-zinc-200 bg-white py-1 pl-3 pr-1 text-xs font-medium text-zinc-600"
                        key={`${file.name}-${file.size}-${file.lastModified}`}
                      >
                        {file.name}
                        <button
                          aria-label={`Remove ${file.name}`}
                          className="grid size-5 place-items-center rounded-full text-zinc-400 transition hover:bg-zinc-100 hover:text-zinc-950"
                          onClick={() => removeFile(file)}
                          type="button"
                        >
                          x
                        </button>
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
              <span className="text-xs text-zinc-500">
                Supports text-based PDFs. Scanned PDFs may require OCR.
              </span>
            </label>

            <label className="mt-5 grid gap-2">
              <span className="text-sm font-semibold text-zinc-800">Manual notes</span>
              <textarea
                className="min-h-40 resize-y rounded-md border border-zinc-300 bg-white px-3 py-3 text-sm leading-6 outline-none focus:border-zinc-950"
                onChange={(event) => setManualNotes(event.target.value)}
                placeholder="Paste call notes, management notes, diligence observations, or key metrics..."
                value={manualNotes}
              />
            </label>

            <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center">
              <button
                className="inline-flex min-h-11 items-center justify-center rounded-md bg-zinc-950 px-5 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-400"
                disabled={isLoading}
                onClick={generateMemo}
                type="button"
              >
                {isLoading ? "Generating memo..." : "Generate Memo"}
              </button>
              {error ? (
                <p className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                  {error}
                </p>
              ) : null}
            </div>
          </div>

          <UploadedFilesCard files={files} onRemoveFile={removeFile} result={result} />
        </section>

        {result ? (
          <>
            <section className="grid gap-5 xl:grid-cols-[0.85fr_1.15fr]">
              <FlightRecorder stages={result.stages} />
              <EvidenceTable evidence={result.evidence} />
            </section>

            <ChartsPanel charts={result.charts} />

            <MemoOutput result={result} />
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
            Memo output, evidence, charts, and export actions will appear after generation.
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
          <Link className="rounded-md bg-zinc-100 px-3 py-2 text-zinc-950 transition hover:bg-zinc-100" href="/memo-pilot">
            Memo Pilot
          </Link>
          <Link className="rounded-md px-3 py-2 transition hover:bg-zinc-100 hover:text-zinc-950" href="/ops-pilot">
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

function UploadedFilesCard({
  files,
  onRemoveFile,
  result,
}: {
  files: File[];
  onRemoveFile: (file: File) => void;
  result: MemoResult | null;
}) {
  const [selectedDocument, setSelectedDocument] = useState<DocumentResult | null>(null);

  return (
    <>
      <section className="rounded-lg border border-zinc-200 bg-zinc-50 p-6 shadow-sm">
        <h2 className="text-xl font-semibold tracking-tight">Uploaded Documents</h2>
        <div className="mt-4 grid gap-3">
          {result?.documents.length ? (
            result.documents.map((document) => (
              <article className="rounded-md border border-zinc-200 bg-white p-4" key={document.filename}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="break-all font-mono text-sm font-semibold text-zinc-950">{document.filename}</p>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-zinc-600">
                      <span className="rounded-full border border-zinc-200 bg-zinc-50 px-2.5 py-1 font-medium">
                        {document.document_type}
                      </span>
                      <span className="rounded-full border border-zinc-200 bg-zinc-50 px-2.5 py-1 font-medium">
                        {document.extraction_status}
                      </span>
                      <span className="rounded-full border border-zinc-200 bg-zinc-50 px-2.5 py-1 font-medium">
                        {document.tables?.length ?? 0} table{(document.tables?.length ?? 0) === 1 ? "" : "s"} extracted
                      </span>
                    </div>
                  </div>
                  <button
                    className="shrink-0 rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-xs font-semibold text-zinc-700 transition hover:bg-zinc-100 hover:text-zinc-950"
                    onClick={() => setSelectedDocument(document)}
                    type="button"
                  >
                    View extraction details
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
              </article>
            ))
          ) : files.length ? (
            files.map((file) => (
              <article className="rounded-md border border-zinc-200 bg-white p-4" key={file.name}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="font-mono text-sm font-semibold text-zinc-950">{file.name}</p>
                  <button
                    className="rounded-md border border-zinc-200 bg-white px-3 py-1.5 text-xs font-semibold text-zinc-600 transition hover:bg-zinc-100 hover:text-zinc-950"
                    onClick={() => onRemoveFile(file)}
                    type="button"
                  >
                    Remove
                  </button>
                </div>
                <p className="mt-2 text-sm text-zinc-500">Ready for extraction</p>
              </article>
            ))
          ) : (
            <p className="rounded-md border border-dashed border-zinc-300 bg-white p-5 text-sm text-zinc-500">
              No documents selected yet.
            </p>
          )}
        </div>
      </section>
      {selectedDocument ? (
        <ExtractionDetailsModal
          document={selectedDocument}
          onClose={() => setSelectedDocument(null)}
        />
      ) : null}
    </>
  );
}

function ExtractionDetailsModal({
  document,
  onClose,
}: {
  document: DocumentResult;
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
                {document.document_type}
              </span>
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
              Extraction summary
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
                No structured tables were extracted from this document.
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
          <li className="grid grid-cols-[40px_minmax(0,1fr)] gap-3" key={stage.name}>
            <span className="grid size-9 place-items-center rounded-md bg-zinc-950 text-xs font-semibold text-white">
              {index + 1}
            </span>
            <div className="rounded-md border border-zinc-200 bg-zinc-50 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold text-zinc-950">{stage.name}</p>
                <span className="text-xs font-medium text-emerald-700">{stage.status}</span>
              </div>
              <p className="mt-2 text-sm leading-6 text-zinc-600">{stage.summary}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function EvidenceTable({ evidence }: { evidence: EvidenceItem[] }) {
  const [showAllEvidence, setShowAllEvidence] = useState(false);
  const visibleEvidence = showAllEvidence ? evidence.slice(0, 24) : evidence.slice(0, 8);

  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold tracking-tight">Evidence Table</h2>
        {evidence.length > 8 ? (
          <button
            className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-xs font-semibold text-zinc-700 transition hover:bg-zinc-100 hover:text-zinc-950"
            onClick={() => setShowAllEvidence((current) => !current)}
            type="button"
          >
            {showAllEvidence ? "Show less" : `Show ${Math.min(evidence.length - 8, 16)} more`}
          </button>
        ) : null}
      </div>
      <div className="mt-5 grid max-h-[720px] gap-3 overflow-auto pr-1">
        {evidence.length ? (
          visibleEvidence.map((item, index) => (
            <article
              className="rounded-md border border-zinc-200 bg-zinc-50 p-4"
              key={`${item.source_document}-${index}`}
            >
              <p className="text-sm leading-7 text-zinc-800">{item.fact}</p>
              <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-zinc-600">
                <span className="rounded-full border border-zinc-200 bg-white px-2.5 py-1 font-medium">
                  {item.evidence_type === "table_row" ? "Table row" : "Text"}
                </span>
                <span className="rounded-full border border-zinc-200 bg-white px-2.5 py-1 font-medium">
                  {item.category}
                </span>
                <span className="rounded-full border border-zinc-200 bg-white px-2.5 py-1 font-medium">
                  {item.support_level}
                </span>
                <span className="min-w-0 break-all rounded-full border border-zinc-200 bg-white px-2.5 py-1 font-mono">
                  {item.source_document}
                </span>
              </div>
            </article>
          ))
        ) : (
          <p className="rounded-md border border-dashed border-zinc-300 bg-zinc-50 p-5 text-sm text-zinc-500">
            No strong evidence extracted.
          </p>
        )}
      </div>
    </section>
  );
}

function ChartsPanel({ charts }: { charts: MemoResult["charts"] }) {
  return (
    <section className="grid gap-5 lg:grid-cols-3">
      <ChartCard title="ARR Growth">
        {charts.arr_growth.length ? (
          charts.arr_growth.map((point) => (
            <Bar key={point.year} label={point.year} value={point.display_value ?? formatCompactCurrency(point.arr)} width={Math.min(100, point.arr / 100000)} />
          ))
        ) : (
          <EmptyChart />
        )}
      </ChartCard>
      <ChartCard title="Evidence Coverage">
        {charts.evidence_completeness.map((point) => (
          <Bar key={point.category} label={point.category} value={`${point.score}%`} width={point.score} />
        ))}
      </ChartCard>
      <ChartCard title="Risk Priority">
        {charts.risk_priority.length ? (
          charts.risk_priority.map((point) => (
            <Bar key={point.risk} label={point.risk} value={`${point.score}`} width={point.score} detail={point.reason} />
          ))
        ) : (
          <EmptyChart />
        )}
      </ChartCard>
    </section>
  );
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
      <h2 className="text-base font-semibold tracking-tight">{title}</h2>
      <div className="mt-4 grid gap-3">{children}</div>
    </section>
  );
}

function Bar({ label, value, width, detail }: { label: string; value: string; width: number; detail?: string }) {
  return (
    <div>
      <div className="mb-1 flex justify-between gap-3 text-xs text-zinc-600">
        <span className="truncate">{label}</span>
        <span>{value}</span>
      </div>
      <div className="h-2 rounded-full bg-zinc-100">
        <div className="h-2 rounded-full bg-zinc-950" style={{ width: `${Math.max(6, width)}%` }} />
      </div>
      {detail ? <p className="mt-1 text-xs leading-5 text-zinc-500">{detail}</p> : null}
    </div>
  );
}

function EmptyChart() {
  return (
    <p className="rounded-md border border-dashed border-zinc-300 bg-zinc-50 p-4 text-sm text-zinc-500">
      Not enough structured data for this chart.
    </p>
  );
}

function MemoOutput({ result }: { result: MemoResult }) {
  const isLlmGenerated = result.memo_generation?.mode === "llm_grounded";

  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Output Sections</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-600">
            {isLlmGenerated
              ? "Memo generated by LLM using extracted source-backed evidence. Guardrails prevent unsupported investment recommendations."
              : "Fallback memo generated from deterministic evidence pipeline. Guardrails prevent unsupported investment recommendations."}
          </p>
        </div>
        <span className="rounded-full border border-zinc-200 bg-zinc-50 px-3 py-1 text-xs font-semibold text-zinc-600">
          {isLlmGenerated ? `LLM: ${result.memo_generation?.model || "configured model"}` : "Deterministic fallback"}
        </span>
      </div>
      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        {memoSections.map(([title, key]) => (
          <article className="rounded-md border border-zinc-200 bg-zinc-50 p-4" key={key}>
            <h3 className="text-sm font-semibold uppercase tracking-[0.08em] text-zinc-500">{title}</h3>
            <p className="mt-3 text-sm leading-6 text-zinc-700">{result.memo[key]}</p>
          </article>
        ))}
        <ListSection title="Key Risks" items={result.memo.key_risks} />
        <div className="grid gap-4 xl:col-span-2 xl:grid-cols-2">
          <ListSection title="Missing Evidence" items={result.memo.missing_evidence} />
          <ListSection title="Reviewer Notes" items={result.memo.reviewer_notes} />
        </div>
        <ListSection title="Diligence Questions" items={result.memo.diligence_questions} wide />
      </div>
    </section>
  );
}

function ListSection({ title, items, wide = false }: { title: string; items: string[]; wide?: boolean }) {
  return (
    <article className={`rounded-md border border-zinc-200 bg-zinc-50 p-4 ${wide ? "xl:col-span-2" : ""}`}>
      <h3 className="text-sm font-semibold uppercase tracking-[0.08em] text-zinc-500">{title}</h3>
      <ul className="mt-3 grid gap-2 text-sm leading-6 text-zinc-700">
        {items.map((item) => (
          <li className="grid grid-cols-[8px_minmax(0,1fr)] gap-3" key={item}>
            <span className="mt-2 size-1.5 rounded-full bg-zinc-950" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </article>
  );
}

function ExportPanel({
  result,
  copied,
  onCopy,
  onDownloadMarkdown,
  onDownloadPdf,
}: {
  result: MemoResult;
  copied: boolean;
  onCopy: () => void;
  onDownloadMarkdown: () => void;
  onDownloadPdf: () => void;
}) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-zinc-50 p-6 shadow-sm">
      <h2 className="text-xl font-semibold tracking-tight">Copy-ready Markdown Artifact</h2>
      <p className="mt-2 text-sm leading-6 text-zinc-600">
        Prepared for review, not for automated investment decisions.
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
      <pre className="mt-5 max-h-[720px] min-h-[520px] overflow-auto whitespace-pre-wrap rounded-md border border-zinc-200 bg-white p-4 font-mono text-xs leading-5 text-zinc-700">
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

function buildPrintableMemo(result: MemoResult, companyName: string, sector: string) {
  const safeMarkdown = result.artifact_markdown
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return `<!doctype html><html><head><title>${companyName || "Diligence Memo"}</title><style>
body{font-family:Inter,Arial,sans-serif;color:#111;background:#fff;margin:40px;line-height:1.55}
h1,h2{border-bottom:1px solid #ddd;padding-bottom:8px} pre{white-space:pre-wrap;font-family:inherit}
.meta{color:#555;font-size:13px;margin-bottom:24px}
</style></head><body><h1>${companyName || "Company"} Diligence Memo Draft</h1><div class="meta">Generated ${new Date(result.generated_at).toLocaleDateString()} · Sector: ${sector || "Not provided"}</div><pre>${safeMarkdown}</pre></body></html>`;
}

function formatCompactCurrency(value: number) {
  if (value >= 1_000_000) {
    return `$${(value / 1_000_000).toFixed(1)}M`;
  }
  if (value >= 1_000) {
    return `$${(value / 1_000).toFixed(1)}K`;
  }
  return `$${new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value)}`;
}

function slugify(value: string) {
  return value.trim().replace(/[^a-z0-9]+/gi, "_").replace(/^_+|_+$/g, "") || "company";
}
