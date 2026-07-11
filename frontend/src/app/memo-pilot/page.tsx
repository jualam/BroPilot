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
};

type EvidenceItem = {
  fact: string;
  source_document: string;
  category: string;
  support_level: string;
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
    arr_growth: { year: string; arr: number }[];
    evidence_completeness: { category: string; score: number }[];
    risk_priority: { risk: string; score: number }[];
  };
  artifact_markdown: string;
  generated_at: string;
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
  const [marketCategory, setMarketCategory] = useState("Fintech");
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
    setFiles(Array.from(event.target.files ?? []));
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
      <section className="mx-auto grid w-full max-w-7xl gap-8 px-5 py-10 sm:px-8 lg:px-10">
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
              <input
                accept="application/pdf"
                className="min-h-12 rounded-md border border-dashed border-zinc-300 bg-zinc-50 px-3 py-3 text-sm text-zinc-700"
                multiple
                onChange={handleFiles}
                type="file"
              />
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

          <UploadedFilesCard files={files} result={result} />
        </section>

        {result ? (
          <>
            <section className="grid gap-5 xl:grid-cols-[0.85fr_1.15fr]">
              <FlightRecorder stages={result.stages} />
              <EvidenceTable evidence={result.evidence} />
            </section>

            <ChartsPanel charts={result.charts} />

            <section className="grid gap-5 xl:grid-cols-[1fr_0.82fr]">
              <MemoOutput result={result} />
              <ExportPanel
                copied={copied}
                onCopy={copyMarkdown}
                onDownloadMarkdown={downloadMarkdown}
                onDownloadPdf={downloadPdf}
                result={result}
              />
            </section>
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

function UploadedFilesCard({ files, result }: { files: File[]; result: MemoResult | null }) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-zinc-50 p-6 shadow-sm">
      <h2 className="text-xl font-semibold tracking-tight">Uploaded Documents</h2>
      <div className="mt-4 grid gap-3">
        {result?.documents.length ? (
          result.documents.map((document) => (
            <article className="rounded-md border border-zinc-200 bg-white p-4" key={document.filename}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="font-mono text-sm font-semibold text-zinc-950">{document.filename}</p>
                <span className="rounded-full border border-zinc-200 bg-zinc-50 px-3 py-1 text-xs font-medium text-zinc-600">
                  {document.document_type}
                </span>
              </div>
              <p className="mt-2 text-xs font-medium uppercase text-zinc-500">{document.extraction_status}</p>
              <p className="mt-2 text-sm leading-6 text-zinc-600">{document.summary}</p>
            </article>
          ))
        ) : files.length ? (
          files.map((file) => (
            <article className="rounded-md border border-zinc-200 bg-white p-4" key={file.name}>
              <p className="font-mono text-sm font-semibold text-zinc-950">{file.name}</p>
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
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm">
      <h2 className="text-xl font-semibold tracking-tight">Evidence Table</h2>
      <div className="mt-5 overflow-hidden rounded-md border border-zinc-200">
        <table className="w-full min-w-[720px] border-collapse text-left text-sm">
          <thead className="bg-zinc-50 text-xs uppercase text-zinc-500">
            <tr>
              <th className="border-b border-zinc-200 p-3">Evidence / fact</th>
              <th className="border-b border-zinc-200 p-3">Source</th>
              <th className="border-b border-zinc-200 p-3">Category</th>
              <th className="border-b border-zinc-200 p-3">Support</th>
            </tr>
          </thead>
          <tbody>
            {evidence.length ? (
              evidence.slice(0, 14).map((item, index) => (
                <tr className="align-top" key={`${item.source_document}-${index}`}>
                  <td className="border-b border-zinc-100 p-3 leading-6 text-zinc-700">{item.fact}</td>
                  <td className="border-b border-zinc-100 p-3 font-mono text-xs text-zinc-600">{item.source_document}</td>
                  <td className="border-b border-zinc-100 p-3 text-zinc-700">{item.category}</td>
                  <td className="border-b border-zinc-100 p-3 text-zinc-700">{item.support_level}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td className="p-5 text-zinc-500" colSpan={4}>
                  No strong evidence extracted.
                </td>
              </tr>
            )}
          </tbody>
        </table>
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
            <Bar key={point.year} label={point.year} value={`$${formatNumber(point.arr)}`} width={Math.min(100, point.arr / 100000)} />
          ))
        ) : (
          <EmptyChart />
        )}
      </ChartCard>
      <ChartCard title="Evidence Completeness">
        {charts.evidence_completeness.map((point) => (
          <Bar key={point.category} label={point.category} value={`${point.score}%`} width={point.score} />
        ))}
      </ChartCard>
      <ChartCard title="Risk Priority">
        {charts.risk_priority.length ? (
          charts.risk_priority.map((point) => (
            <Bar key={point.risk} label={point.risk} value={`${point.score}`} width={point.score} />
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

function Bar({ label, value, width }: { label: string; value: string; width: number }) {
  return (
    <div>
      <div className="mb-1 flex justify-between gap-3 text-xs text-zinc-600">
        <span className="truncate">{label}</span>
        <span>{value}</span>
      </div>
      <div className="h-2 rounded-full bg-zinc-100">
        <div className="h-2 rounded-full bg-zinc-950" style={{ width: `${Math.max(6, width)}%` }} />
      </div>
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
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm">
      <h2 className="text-xl font-semibold tracking-tight">Output Sections</h2>
      <div className="mt-5 grid gap-4">
        {memoSections.map(([title, key]) => (
          <article className="rounded-md border border-zinc-200 bg-zinc-50 p-4" key={key}>
            <h3 className="text-sm font-semibold uppercase tracking-[0.08em] text-zinc-500">{title}</h3>
            <p className="mt-3 text-sm leading-6 text-zinc-700">{result.memo[key]}</p>
          </article>
        ))}
        <ListSection title="Key Risks" items={result.memo.key_risks} />
        <ListSection title="Missing Evidence" items={result.memo.missing_evidence} />
        <ListSection title="Diligence Questions" items={result.memo.diligence_questions} />
        <ListSection title="Reviewer Notes" items={result.memo.reviewer_notes} />
      </div>
    </section>
  );
}

function ListSection({ title, items }: { title: string; items: string[] }) {
  return (
    <article className="rounded-md border border-zinc-200 bg-zinc-50 p-4">
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
      <pre className="mt-5 max-h-[640px] overflow-auto whitespace-pre-wrap rounded-md border border-zinc-200 bg-white p-4 font-mono text-xs leading-5 text-zinc-700">
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

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
}

function slugify(value: string) {
  return value.trim().replace(/[^a-z0-9]+/gi, "_").replace(/^_+|_+$/g, "") || "company";
}
