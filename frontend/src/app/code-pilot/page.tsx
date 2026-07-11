"use client";

import type { FormEvent, ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

const API_URL = "http://127.0.0.1:8000/api/runs/start";
const REPO_STATUS_API_URL = "http://127.0.0.1:8000/api/runs/repo-status";
const REVERT_API_URL = "http://127.0.0.1:8000/api/runs";
const REVIEW_API_URL = "http://127.0.0.1:8000/api/review/file-diff";
const DEFAULT_REPO_PATH = "D:\\bropilot-demo";
const DEFAULT_TASK = "";

type AgentStep = {
  name: string;
  status: string;
  summary: string;
  details: string;
};

type ChangedFile = {
  path: string;
  change_type: string;
  summary: string;
  additions?: number;
  deletions?: number;
  diff_stat?: string;
  before_contents?: string;
  after_contents?: string;
  content_truncated?: boolean;
};

type TestResults = {
  command: string;
  status: string;
  summary: string;
};

type BlockedAction = {
  command: string;
  reason: string;
};

type SafetyReport = {
  risk_score: string;
  risk_reason?: string;
  blocked_actions: BlockedAction[];
};

type MemoryReport = {
  before: string[];
  learned: string[];
  used: string[];
};

type PrSummary = {
  title: string;
  body: string[];
  markdown?: string;
};

type RunResponse = {
  run_id: string;
  status: string;
  repo_path: string;
  task: string;
  started_at: string;
  completed_at: string;
  agents: AgentStep[];
  changed_files: ChangedFile[];
  tests: TestResults;
  safety: SafetyReport;
  memory: MemoryReport;
  pr_summary: PrSummary;
};

type RepoStatus = {
  status: "clean" | "dirty" | "missing" | "error";
  label: string;
  changed_count: number;
  changed_files: string[];
  message: string;
};

type RevertResult = {
  status: string;
  message: string;
  restored_files: number;
  removed_files: number;
};

const statusTone: Record<string, string> = {
  completed: "bg-emerald-400/10 text-emerald-300 ring-emerald-400/20",
  passed: "bg-emerald-400/10 text-emerald-300 ring-emerald-400/20",
  running: "bg-sky-400/10 text-sky-300 ring-sky-400/20",
  failed: "bg-red-400/10 text-red-300 ring-red-400/20",
  blocked: "bg-orange-400/10 text-orange-300 ring-orange-400/20",
  needs_attention: "bg-amber-400/10 text-amber-300 ring-amber-400/20",
  skipped: "bg-[#18191b] text-zinc-400 ring-white/10",
  low: "bg-emerald-400/10 text-emerald-300 ring-emerald-400/20",
  medium: "bg-amber-400/10 text-amber-300 ring-amber-400/20",
  high: "bg-red-400/10 text-red-300 ring-red-400/20",
};

function getStatusTone(status: string) {
  return (
    statusTone[status.toLowerCase()] ?? "bg-[#18191b] text-zinc-400 ring-white/10"
  );
}

function getRiskExplanation(risk: string) {
  const normalized = risk.toLowerCase();

  if (normalized === "low") {
    return "Clean review signal: Code Pilot changed files, git status was captured, and pytest passed.";
  }

  if (normalized === "medium") {
    return "Review needed: BroPilot captured the patch, but the run needs attention before it is treated as ready.";
  }

  if (normalized === "high") {
    return "High attention: BroPilot could not reliably capture the final review state.";
  }

  return "BroPilot summarizes safety from the agent result, git status, and pytest verification.";
}

function StatusPill({ value }: { value: string }) {
  return (
    <span
      className={`inline-flex min-h-7 items-center rounded-full px-3 text-xs font-medium ring-1 ${getStatusTone(
        value,
      )}`}
    >
      {value.replace("_", " ")}
    </span>
  );
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <span
      className={`size-2.5 shrink-0 border-b border-r border-zinc-500 transition-transform ${
        open ? "rotate-[225deg]" : "rotate-45"
      }`}
    />
  );
}

function Panel({
  title,
  eyebrow,
  children,
  className = "",
}: {
  title: string;
  eyebrow?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`min-w-0 rounded-lg border border-white/10 bg-[#18191b] p-5 shadow-[0_1px_1px_rgba(0,0,0,0.04),0_14px_40px_rgba(0,0,0,0.07)] ${className}`}
    >
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          {eyebrow ? (
            <p className="mb-2 text-xs font-medium uppercase text-zinc-500">
              {eyebrow}
            </p>
          ) : null}
          <h2 className="text-xl font-semibold text-zinc-50">{title}</h2>
        </div>
      </div>
      {children}
    </section>
  );
}

function EmptyPanel({ label }: { label: string }) {
  return (
    <div className="rounded-md border border-dashed border-white/10 bg-[#101113] p-5 text-sm text-zinc-500">
      {label}
    </div>
  );
}

function RepoStatusBanner({
  status,
  isChecking,
}: {
  status: RepoStatus | null;
  isChecking: boolean;
}) {
  const visibleStatus = status ?? {
    status: "error",
    label: "Repo status waiting",
    changed_count: 0,
    changed_files: [],
    message: "Enter a repo path to check whether the next run starts clean.",
  };
  const tone =
    visibleStatus.status === "clean"
      ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-200"
      : visibleStatus.status === "dirty"
        ? "border-amber-400/20 bg-amber-400/10 text-amber-200"
        : "border-white/10 bg-[#111214] text-zinc-300";
  const dot =
    visibleStatus.status === "clean"
      ? "bg-emerald-300"
      : visibleStatus.status === "dirty"
        ? "bg-amber-300"
        : "bg-zinc-500";

  return (
    <div className={`rounded-[8px] border px-4 py-3 ${tone}`}>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-center gap-2">
          <span className={`size-2 shrink-0 rounded-full ${dot}`} />
          <p className="text-sm font-semibold">
            {isChecking ? "Checking repo status..." : visibleStatus.label}
          </p>
        </div>
        {visibleStatus.status === "dirty" ? (
          <span className="text-xs font-medium">
            {visibleStatus.changed_count} changed file
            {visibleStatus.changed_count === 1 ? "" : "s"}
          </span>
        ) : null}
      </div>
      <p className="mt-2 text-xs leading-5 opacity-80">{visibleStatus.message}</p>
    </div>
  );
}

function WorkflowSteps() {
  const steps = [
    "Repo context",
    "Scoped plan",
    "Constrained agent",
    "Independent tests",
    "Diff + PR summary",
  ];

  return (
    <section className="rounded-lg border border-white/10 bg-[#18191b] p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-center gap-2">
        {steps.map((step, index) => (
          <div className="flex items-center gap-2" key={step}>
            <span className="rounded-md border border-white/10 bg-[#111214] px-3 py-2 text-xs font-medium text-zinc-300">
              {step}
            </span>
            {index < steps.length - 1 ? (
              <span className="text-xs text-zinc-300">-&gt;</span>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  );
}

function TopNav() {
  return (
    <header className="sticky top-0 z-20 border-b border-white/10 bg-[#0b0b0c]/90 backdrop-blur">
      <nav className="mx-auto flex min-h-16 w-full max-w-7xl items-center justify-between gap-6 px-5 sm:px-8 lg:px-10">
        <a
          aria-label="BroPilot Workbench home"
          className="flex shrink-0 items-center gap-3"
          href="/"
        >
          <span className="grid size-9 place-items-center rounded-lg border border-white/10 bg-white text-zinc-950 shadow-[0_1px_18px_rgba(255,255,255,0.08)]">
            <span className="relative block size-4">
              <span className="absolute left-0 top-0 h-4 w-3 rounded-sm bg-zinc-950 [clip-path:polygon(0_0,100%_50%,0_100%)]" />
              <span className="absolute right-0 top-1.5 size-1.5 rounded-full bg-zinc-950" />
            </span>
          </span>
          <span className="grid leading-tight">
            <span className="text-sm font-semibold text-zinc-50">BroPilot</span>
            <span className="text-xs text-zinc-500">Workbench</span>
          </span>
        </a>
        <div className="hidden items-center gap-1 text-sm text-zinc-400 md:flex">
          <a className="rounded-md px-3 py-2 transition hover:bg-[#18191b] hover:text-zinc-50" href="/">
            Home
          </a>
          <a className="rounded-md bg-[#18191b] px-3 py-2 text-zinc-50 transition hover:bg-[#18191b]" href="/code-pilot">
            Code Pilot
          </a>
          <a className="rounded-md px-3 py-2 transition hover:bg-[#18191b] hover:text-zinc-50" href="/memo-pilot">
            Memo Pilot
          </a>
          <a className="rounded-md px-3 py-2 transition hover:bg-[#18191b] hover:text-zinc-50" href="/ops-pilot">
            Ops Pilot
          </a>
          <a className="rounded-md px-3 py-2 transition hover:bg-[#18191b] hover:text-zinc-50" href="/architecture">
            Workflow Pattern
          </a>
        </div>
      </nav>
    </header>
  );
}

export default function Home() {
  const [repoPath, setRepoPath] = useState(DEFAULT_REPO_PATH);
  const [task, setTask] = useState(DEFAULT_TASK);
  const [run, setRun] = useState<RunResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openAgentLogs, setOpenAgentLogs] = useState<Record<string, boolean>>({});
  const [showTestLog, setShowTestLog] = useState(false);
  const [diffFile, setDiffFile] = useState<ChangedFile | null>(null);
  const [repoStatus, setRepoStatus] = useState<RepoStatus | null>(null);
  const [isCheckingRepo, setIsCheckingRepo] = useState(false);
  const [revertResult, setRevertResult] = useState<RevertResult | null>(null);
  const [isReverting, setIsReverting] = useState(false);
  const [showRevertDialog, setShowRevertDialog] = useState(false);

  const runMeta = useMemo(() => {
    if (!run) {
      return null;
    }

    return [
      { label: "Run", value: run.run_id },
      { label: "Status", value: run.status.replace("_", " ") },
      { label: "Changed", value: `${run.changed_files.length} files` },
      { label: "Tests", value: run.tests.status },
      { label: "Started", value: formatDateTime(run.started_at) },
      { label: "Completed", value: formatDateTime(run.completed_at) },
    ];
  }, [run]);

  async function startRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoading(true);
    setError(null);
    setOpenAgentLogs({});
    setShowTestLog(false);
    setDiffFile(null);
    setRevertResult(null);
    setShowRevertDialog(false);

    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          repo_path: repoPath,
          task,
        }),
      });

      if (!response.ok) {
        throw new Error(`Backend returned ${response.status}`);
      }

      const data = (await response.json()) as RunResponse;
      setRun(data);
    } catch (caughtError) {
      const message =
        caughtError instanceof Error
          ? caughtError.message
          : "BroPilot could not reach the backend.";

      setError(
        `${message}. Confirm FastAPI is running at http://127.0.0.1:8000.`,
      );
    } finally {
      setIsLoading(false);
    }
  }

  function toggleAgentLog(name: string) {
    setOpenAgentLogs((current) => ({
      ...current,
      [name]: !current[name],
    }));
  }

  function openDiff(file: ChangedFile) {
    setDiffFile(file);
  }

  function closeDiff() {
    if (typeof window !== "undefined" && window.location.hash === "#diff") {
      window.history.replaceState(null, "", window.location.pathname);
    }

    setDiffFile(null);
  }

  useEffect(() => {
    const trimmedPath = repoPath.trim();

    if (!trimmedPath) {
      setRepoStatus(null);
      return;
    }

    const controller = new AbortController();
    const timeout = window.setTimeout(async () => {
      setIsCheckingRepo(true);

      try {
        const response = await fetch(
          `${REPO_STATUS_API_URL}?repo_path=${encodeURIComponent(trimmedPath)}`,
          { signal: controller.signal },
        );

        if (!response.ok) {
          throw new Error(`Backend returned ${response.status}`);
        }

        const data = (await response.json()) as RepoStatus;
        setRepoStatus(data);
      } catch (caughtError) {
        if (caughtError instanceof DOMException && caughtError.name === "AbortError") {
          return;
        }

        setRepoStatus({
          status: "error",
          label: "Repo status unavailable",
          changed_count: 0,
          changed_files: [],
          message: "Start the backend to check whether the repo is clean.",
        });
      } finally {
        if (!controller.signal.aborted) {
          setIsCheckingRepo(false);
        }
      }
    }, 350);

    return () => {
      controller.abort();
      window.clearTimeout(timeout);
    };
  }, [repoPath]);

  useEffect(() => {
    if (!diffFile || typeof window === "undefined") {
      return;
    }

    if (window.location.hash !== "#diff") {
      window.history.pushState({ codePilotDiff: true }, "", "#diff");
    }

    function closeOnBrowserBack() {
      setDiffFile(null);
    }

    window.addEventListener("popstate", closeOnBrowserBack);

    return () => {
      window.removeEventListener("popstate", closeOnBrowserBack);
    };
  }, [diffFile]);

  const testSummary = run ? parseTestSummary(run) : null;
  const isRunReverted = revertResult?.status === "restored";

  async function revertRun() {
    if (!run || isReverting) {
      return;
    }

    setIsReverting(true);
    setRevertResult(null);

    try {
      const response = await fetch(`${REVERT_API_URL}/${run.run_id}/revert`, {
        method: "POST",
      });

      if (!response.ok) {
        throw new Error(`Backend returned ${response.status}`);
      }

      const data = (await response.json()) as RevertResult;
      setRevertResult(data);
      setShowRevertDialog(false);
    } catch (caughtError) {
      const message =
        caughtError instanceof Error
          ? caughtError.message
          : "Could not restore the checkpoint.";

      setRevertResult({
        status: "error",
        message,
        restored_files: 0,
        removed_files: 0,
      });
    } finally {
      setIsReverting(false);
    }
  }

  return (
    <main className="code-pilot-shell min-h-screen bg-[#09090a] text-zinc-100">
      <TopNav />
      <div className="mx-auto flex w-full max-w-[1199px] flex-col gap-6 px-5 py-6 sm:px-8 lg:px-10">

        <section className="mx-auto max-w-3xl py-4 text-center">
          <h1 className="font-copperplate text-5xl font-semibold leading-none text-zinc-50 sm:text-6xl lg:text-7xl">
            Code Pilot
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg leading-7 text-zinc-400 sm:text-xl">
            Turn an engineering task into a review-ready code change with
            scoped context, constrained execution, tests, diffs, safety checks,
            and a PR summary.
          </p>
        </section>

        <WorkflowSteps />

        <section className="grid min-w-0 gap-6 lg:grid-cols-[minmax(0,1.06fr)_minmax(380px,0.94fr)]">
          <div className="min-w-0 rounded-lg border border-white/10 bg-[#18191b] p-6 shadow-[0_1px_1px_rgba(0,0,0,0.04),0_14px_40px_rgba(0,0,0,0.07)] sm:p-8">
            <form className="grid gap-4" onSubmit={startRun}>
              <label className="grid gap-2">
                <span className="text-sm font-medium text-zinc-300">
                  Repo path
                </span>
                <input
                  className="min-h-12 rounded-md border border-white/10 bg-[#111214] px-4 text-sm text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                  value={repoPath}
                  onChange={(event) => setRepoPath(event.target.value)}
                  placeholder="D:\\bropilot-demo"
                  required
                  suppressHydrationWarning
                />
              </label>

              <label className="grid gap-2">
                <span className="text-sm font-medium text-zinc-300">Task</span>
                <textarea
                  className="min-h-32 resize-y rounded-md border border-white/10 bg-[#111214] px-4 py-3 text-sm leading-6 text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                  value={task}
                  onChange={(event) => setTask(event.target.value)}
                  placeholder="Describe the code change Code Pilot should prepare"
                  required
                  suppressHydrationWarning
                />
              </label>

              <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                <button
                  className="inline-flex min-h-11 items-center justify-center rounded-md bg-white px-4 text-sm font-semibold text-zinc-950 transition hover:bg-zinc-200 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-400"
                  disabled={isLoading}
                  type="submit"
                  suppressHydrationWarning
                >
                  {isLoading ? "Running Code Pilot..." : "Run Code Pilot"}
                </button>
                {error ? (
                  <p className="rounded-md border border-red-400/20 bg-red-400/10 px-4 py-3 text-sm text-red-300">
                    {error}
                  </p>
                ) : null}
              </div>
              <RepoStatusBanner
                isChecking={isCheckingRepo}
                status={repoStatus}
              />
            </form>
          </div>

          <RunSummaryCard run={run} runMeta={runMeta} />
        </section>

        <section className="min-w-0">
          <Panel title="Agent Flight Recorder">
            {run ? (
              <ol className="grid gap-4">
                {run.agents.map((agent, index) => (
                  <AgentTimelineCard
                    agent={agent}
                    index={index}
                    isLast={index === run.agents.length - 1}
                    key={agent.name}
                    run={run}
                    showLog={Boolean(openAgentLogs[agent.name])}
                    toggleLog={() => toggleAgentLog(agent.name)}
                  />
                ))}
              </ol>
            ) : (
              <EmptyPanel label="No run captured yet." />
            )}
          </Panel>
        </section>

        <section className="grid min-w-0 gap-6 lg:grid-cols-2">
          <ChangedFilesPanel
            isRunReverted={isRunReverted}
            run={run}
            onOpenDiff={openDiff}
          />
          <Panel title="Test Results">
            {run && testSummary ? (
              <div className="rounded-[8px] border border-white/10 bg-[#111214] p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="text-sm font-semibold text-zinc-50">
                      {run.tests.command} {run.tests.status}
                    </p>
                    <p className="mt-2 text-sm text-zinc-400">
                      {testSummary.label}
                    </p>
                  </div>
                  <StatusPill value={run.tests.status} />
                </div>
                <button
                  className="mt-4 inline-flex items-center gap-2 rounded-[6px] bg-[#18191b] px-3 py-2 text-xs font-medium text-zinc-300 border border-white/10 transition hover:text-zinc-50"
                  onClick={() => setShowTestLog((current) => !current)}
                  type="button"
                >
                  <span>{showTestLog ? "Hide test log" : "Show test log"}</span>
                  <ChevronIcon open={showTestLog} />
                </button>
                {showTestLog ? (
                  <pre className="mt-3 max-h-56 w-full max-w-full overflow-auto whitespace-pre-wrap break-words rounded-[10px] bg-[#18191b] p-3 font-mono text-xs leading-5 text-zinc-300 border border-white/10">
                    {getTesterLog(run)}
                  </pre>
                ) : null}
              </div>
            ) : (
              <EmptyPanel label="Test output is waiting for execution." />
            )}
          </Panel>
        </section>

        <section className="grid min-w-0 gap-6 lg:grid-cols-[0.75fr_1.25fr]">
          <Panel title="Safety Panel">
            {run ? (
              <div className="grid gap-4">
                <div className="rounded-[8px] border border-white/10 bg-[#111214] p-4">
                  <div className="flex flex-wrap items-center gap-3">
                    <p className="text-sm font-semibold text-zinc-50">
                      Review signal
                    </p>
                    <StatusPill value={run.safety.risk_score} />
                  </div>
                  <p className="mt-3 text-sm leading-6 text-zinc-300">
                    {run.safety.risk_reason ??
                      getRiskExplanation(run.safety.risk_score)}
                  </p>
                </div>
                <div className="grid gap-3">
                  {run.safety.blocked_actions.map((action) => (
                    <article
                      className="rounded-[8px] border border-white/10 bg-[#111214] p-4"
                      key={action.command}
                    >
                      <p className="text-sm font-semibold text-zinc-50">
                        {action.command}
                      </p>
                      <p className="mt-3 text-sm leading-6 text-zinc-300">
                        {action.reason}
                      </p>
                    </article>
                  ))}
                </div>
              </div>
            ) : (
              <EmptyPanel label="Blocked actions and risk score will appear here." />
            )}
          </Panel>

          <RecoveryPanel
            isReverting={isReverting}
            onRevert={() => setShowRevertDialog(true)}
            result={revertResult}
            run={run}
          />
        </section>

        <section className="min-w-0">
          <Panel
            title="Memory Panel"
          >
            {run ? (
              <div className="grid gap-4 md:grid-cols-3">
                {(() => {
                  const memory = buildMemoryDisplay(run.memory);

                  return (
                    <>
                      <MemoryColumn
                        title="Before this run"
                        description="Curated repo facts Code Pilot already had."
                        items={memory.before}
                        expandedItems={memory.beforeAll}
                        expandedLabel="Show all memory"
                      />
                      <MemoryColumn
                        title="Used in prompt"
                        description="Memory and guardrails sent into the OpenAI agent."
                        items={memory.used}
                      />
                      <MemoryColumn
                        title="Learned after this run"
                        description="New memory recorded after verification."
                        items={memory.learned}
                        featured
                      />
                    </>
                  );
                })()}
              </div>
            ) : (
              <EmptyPanel label="Code Pilot memory will grow from each reviewed run." />
            )}
          </Panel>
        </section>

        <PrSummaryPanel run={run} />
        <DiffViewer
          file={diffFile}
          onClose={closeDiff}
          task={run?.task ?? ""}
        />
        <RevertConfirmDialog
          isOpen={showRevertDialog}
          isReverting={isReverting}
          onCancel={() => setShowRevertDialog(false)}
          onConfirm={revertRun}
          run={run}
        />
      </div>
    </main>
  );
}

function RunSummaryCard({
  run,
  runMeta,
}: {
  run: RunResponse | null;
  runMeta: { label: string; value: string }[] | null;
}) {
  return (
    <div className="min-w-0 rounded-lg border border-white/10 bg-[#18191b] p-6 shadow-[0_1px_1px_rgba(0,0,0,0.04),0_14px_40px_rgba(0,0,0,0.07)] sm:p-8">
      <div className="flex h-full flex-col justify-between">
        <div>
          <p className="mb-4 text-sm font-medium text-zinc-400">Current run</p>
          {run ? (
            <>
              <div className="mb-4 flex flex-wrap items-center gap-2">
                <StatusPill value={run.status} />
                <span className="rounded-full border border-white/10 bg-[#111214] px-3 py-1.5 text-xs text-zinc-400">
                  CLI disabled
                </span>
                <span className="rounded-full border border-white/10 bg-[#111214] px-3 py-1.5 text-xs text-zinc-400">
                  Human review required
                </span>
              </div>
              <div className="rounded-md border border-white/10 bg-[#111214] p-4">
                <p className="text-xs font-medium uppercase text-zinc-500">
                  Task
                </p>
                <p className="mt-3 text-sm font-medium leading-6 text-zinc-300">
                  {run.task}
                </p>
              </div>
            </>
          ) : (
            <>
              <h2 className="text-3xl font-semibold leading-tight text-zinc-50">
                Ready to launch Code Pilot.
              </h2>
              <p className="mt-4 text-sm leading-6 text-zinc-400">
                Submit an engineering task to watch the agent edit, Code Pilot
                verify, and the dashboard package the result for review.
              </p>
            </>
          )}
        </div>

        <div className="mt-8 grid grid-cols-2 gap-3 xl:grid-cols-3">
          {runMeta ? (
            runMeta.map((item) => (
              <div
                className="rounded-md border border-white/10 bg-[#111214] p-4"
                key={item.label}
              >
                <p className="text-xs text-zinc-500">{item.label}</p>
                <p className="mt-2 break-words text-sm font-medium text-zinc-50">
                  {item.value}
                </p>
              </div>
            ))
          ) : (
            <>
              <div className="rounded-md border border-white/10 bg-[#111214] p-4">
                <p className="text-xs text-zinc-500">Workflow</p>
                <p className="mt-2 text-sm font-medium text-zinc-50">5 agents</p>
              </div>
              <div className="rounded-md border border-white/10 bg-[#111214] p-4">
                <p className="text-xs text-zinc-500">Runner</p>
                <p className="mt-2 text-sm font-medium text-zinc-50">
                  OpenAI Agents SDK
                </p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function AgentTimelineCard({
  agent,
  index,
  isLast,
  run,
  showLog,
  toggleLog,
}: {
  agent: AgentStep;
  index: number;
  isLast: boolean;
  run: RunResponse;
  showLog: boolean;
  toggleLog: () => void;
}) {
  const highlights = getAgentHighlights(agent, run);
  const hasTechnicalLog = agent.details.trim().length > 0;
  const displaySummary =
    agent.name === "Tester Agent" ? parseTestSummary(run).label : agent.summary;

  return (
    <li className="grid min-w-0 gap-4 sm:grid-cols-[48px_minmax(0,1fr)]">
      <div className="flex items-start gap-3 sm:flex-col sm:items-center">
        <div className="grid size-12 shrink-0 place-items-center rounded-full border border-white/10 bg-[#18191b] text-sm font-semibold text-zinc-100">
          {index + 1}
        </div>
        {!isLast ? (
          <div className="hidden h-full min-h-12 w-px bg-[#18191b] sm:block" />
        ) : null}
      </div>
      <article className="min-w-0 rounded-[8px] border border-white/10 bg-[#111214] p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h3 className="text-base font-semibold text-zinc-50">{agent.name}</h3>
            <p className="mt-2 text-sm leading-6 text-zinc-400">
              {displaySummary}
            </p>
          </div>
          <StatusPill value={agent.status} />
        </div>

        {highlights.length ? (
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            {highlights.map((highlight) => (
              <div
                className="rounded-[6px] bg-[#18191b] px-3 py-2 text-sm text-zinc-300 border border-white/10"
                key={highlight}
              >
                {highlight}
              </div>
            ))}
          </div>
        ) : null}

        {hasTechnicalLog ? (
          <>
            <button
              className="mt-4 inline-flex items-center gap-2 rounded-[6px] bg-[#18191b] px-3 py-2 text-xs font-medium text-zinc-300 border border-white/10 transition hover:text-zinc-50"
              onClick={toggleLog}
              type="button"
            >
              <span>{showLog ? "Hide technical log" : "Show technical log"}</span>
              <ChevronIcon open={showLog} />
            </button>
            {showLog ? (
              <TechnicalLog agent={agent} run={run} />
            ) : null}
          </>
        ) : null}
      </article>
    </li>
  );
}

function TechnicalLog({ agent, run }: { agent: AgentStep; run: RunResponse }) {
  if (agent.name === "Analyzer Agent") {
    const rows = parseGitStatusRows(agent.details);

    return (
      <div className="mt-3 rounded-[10px] bg-[#18191b] p-3 border border-white/10">
        <p className="text-xs font-semibold uppercase text-zinc-500">
          Git status before run
        </p>
        {rows.length ? (
          <div className="mt-3 grid gap-2">
            {rows.map((row) => (
              <div
                className="grid min-w-0 grid-cols-[42px_minmax(0,1fr)] items-center gap-3 rounded-[8px] border border-white/10 bg-[#111214] px-3 py-2"
                key={`${row.status}-${row.path}`}
              >
                <span className="inline-flex min-h-6 items-center justify-center rounded-[5px] bg-[#18191b] px-2 font-mono text-[11px] text-zinc-300">
                  {row.status}
                </span>
                <span className="min-w-0 break-all font-mono text-xs text-zinc-300">
                  {row.path}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-3 text-sm text-zinc-300">Working tree was clean.</p>
        )}
      </div>
    );
  }

  if (agent.name === "Coder Agent") {
    return <CoderTechnicalLog details={agent.details} run={run} />;
  }

  if (agent.name === "Planner Agent") {
    return <PlannerTechnicalLog details={agent.details} />;
  }

  return (
    <pre className="mt-3 max-h-64 w-full max-w-full overflow-auto whitespace-pre-wrap break-words rounded-[10px] bg-[#18191b] p-3 font-mono text-xs leading-5 text-zinc-300 border border-white/10">
      {agent.details}
    </pre>
  );
}

function PlannerTechnicalLog({ details }: { details: string }) {
  const sections = parsePlannerLog(details);

  return (
    <div className="mt-3 grid max-h-[720px] gap-3 overflow-auto rounded-[10px] bg-[#18191b] p-4 border border-white/10">
      <div className="grid gap-3 lg:grid-cols-[0.8fr_1.2fr]">
        <LogBlock title="Selected model" lines={sections.model} accent />
        <LogBlock title="Planner summary" lines={sections.summary} />
      </div>

      <LogBlock title="Structured plan" lines={sections.plan} />
      <LogBlock title="Context sent to Code Pilot" lines={sections.context} />
      <LogBlock title="Guardrails" lines={sections.guardrails} mono />
      <LogBlock title="Raw planner log" lines={sections.other} mono />
    </div>
  );
}

function LogBlock({
  title,
  lines,
  mono = false,
  accent = false,
}: {
  title: string;
  lines: string[];
  mono?: boolean;
  accent?: boolean;
}) {
  if (!lines.length) {
    return null;
  }

  return (
    <section className="min-w-0 rounded-[8px] border border-white/10 bg-[#111214] p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-zinc-500">
        {title}
      </p>
      <div
        className={`mt-3 min-w-0 rounded-[7px] border px-3 py-2 text-sm leading-6 ${
          accent
            ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-200"
            : "border-white/10 bg-[#18191b] text-zinc-300"
        } ${mono ? "font-mono text-xs" : ""}`}
      >
        {lines.map((line, index) => (
          <p
            className="min-w-0 whitespace-pre-wrap break-words py-1.5"
            key={`${title}-line-${index}`}
          >
            {line}
          </p>
        ))}
      </div>
    </section>
  );
}

function CoderTechnicalLog({
  details,
  run,
}: {
  details: string;
  run: RunResponse;
}) {
  const sections = parseCoderLog(details);

  return (
    <div className="mt-3 grid gap-3 rounded-[10px] bg-[#18191b] p-3 border border-white/10">
      <div>
        <p className="text-xs font-semibold uppercase text-zinc-500">
          Code changes
        </p>
        <div className="mt-3 grid gap-2">
          {run.changed_files.map((file) => (
            <div
              className="flex min-w-0 flex-wrap items-center gap-2 rounded-[8px] border border-white/10 bg-[#111214] px-3 py-2"
              key={file.path}
            >
              <span className="min-w-0 break-all font-mono text-xs font-semibold text-zinc-50">
                {file.path}
              </span>
              <span className="rounded-full bg-emerald-400/10 px-2 py-1 text-[11px] text-emerald-300">
                +{file.additions ?? 0}
              </span>
              <span className="rounded-full bg-red-400/10 px-2 py-1 text-[11px] text-red-300">
                -{file.deletions ?? 0}
              </span>
            </div>
          ))}
        </div>
      </div>

      <LogSection title="Run setup" lines={sections.setup} />
      <LogSection title="Repair loop" lines={sections.repair} />
      <LogSection title="Agent tool calls" lines={sections.tools} mono />
      <LogSection title="Assistant notes" lines={sections.assistant} />
      <LogSection title="Raw remainder" lines={sections.other} mono />
    </div>
  );
}

function LogSection({
  title,
  lines,
  mono = false,
}: {
  title: string;
  lines: string[];
  mono?: boolean;
}) {
  if (!lines.length) {
    return null;
  }

  return (
    <div>
      <p className="text-xs font-semibold uppercase text-zinc-500">{title}</p>
      <div className="mt-2 grid gap-2">
        {lines.map((line, index) => (
          <div
            className={`min-w-0 rounded-[8px] border border-white/10 bg-[#111214] px-3 py-2 text-xs leading-5 text-zinc-300 ${
              mono ? "font-mono" : ""
            }`}
            key={`${title}-${index}`}
          >
            {line}
          </div>
        ))}
      </div>
    </div>
  );
}

function ChangedFilesPanel({
  run,
  onOpenDiff,
  isRunReverted = false,
}: {
  run: RunResponse | null;
  onOpenDiff: (file: ChangedFile) => void;
  isRunReverted?: boolean;
}) {
  return (
    <Panel title="Changed Files">
      {run ? (
        run.changed_files.length ? (
          <div className="grid gap-3">
            {isRunReverted ? (
              <div className="rounded-[8px] border border-sky-400/20 bg-sky-400/10 p-4 text-sm leading-6 text-sky-100">
                This is the historical diff from the completed run. The local
                repo has been restored to the checkpoint captured before this
                run.
              </div>
            ) : null}
            {run.changed_files.map((file) => (
              <article
                className="rounded-[8px] border border-white/10 bg-[#111214] p-4"
                key={file.path}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="break-all font-mono text-sm text-zinc-50">
                      {file.path}
                    </p>
                    <p className="mt-2 text-sm leading-6 text-zinc-400">
                      {file.summary}
                    </p>
                  </div>
                  <StatusPill value={file.change_type} />
                </div>
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-emerald-400/10 px-3 py-1.5 text-xs font-medium text-emerald-300 ring-1 ring-emerald-400/20">
                    +{file.additions ?? 0}
                  </span>
                  <span className="rounded-full bg-red-400/10 px-3 py-1.5 text-xs font-medium text-red-300 ring-1 ring-red-400/20">
                    -{file.deletions ?? 0}
                  </span>
                  {file.diff_stat ? (
                    <span className="font-mono text-xs text-zinc-500">
                      {file.diff_stat}
                    </span>
                  ) : null}
                  <button
                    className="ml-auto rounded-[6px] bg-[#18191b] px-3 py-1.5 text-xs font-medium text-zinc-300 ring-1 ring-white/10 transition hover:bg-[#18191b] hover:text-zinc-50"
                    onClick={() => onOpenDiff(file)}
                    type="button"
                  >
                    See diff
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyPanel label="No code changes were captured for this run." />
        )
      ) : (
        <EmptyPanel label="Changed files will appear after a run." />
      )}
    </Panel>
  );
}

function RecoveryPanel({
  run,
  isReverting,
  result,
  onRevert,
}: {
  run: RunResponse | null;
  isReverting: boolean;
  result: RevertResult | null;
  onRevert: () => void;
}) {
  return (
    <Panel title="Recovery">
      {run ? (
        <div className="rounded-[8px] border border-white/10 bg-[#111214] p-4">
          <p className="text-sm font-semibold text-zinc-50">
            Local checkpoint captured before this run.
          </p>
          <p className="mt-2 text-sm leading-6 text-zinc-400">
            Restore the target repo to its pre-run state without committing,
            pushing, or touching GitHub. Earlier local changes remain if they
            existed before this run.
          </p>
          <button
            className="mt-4 inline-flex min-h-10 items-center justify-center rounded-md border border-red-400/20 bg-red-400/10 px-4 text-sm font-semibold text-red-200 transition hover:bg-red-400/15 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isReverting}
            onClick={onRevert}
            type="button"
          >
            {isReverting ? "Restoring checkpoint..." : "Revert this run"}
          </button>
          {result ? (
            <div className="mt-4 rounded-[8px] border border-white/10 bg-[#18191b] p-3 text-sm leading-6 text-zinc-300">
              <p className="font-semibold text-zinc-50">{result.message}</p>
              <p className="mt-1 text-xs text-zinc-500">
                Restored {result.restored_files} file
                {result.restored_files === 1 ? "" : "s"}; removed{" "}
                {result.removed_files} new file
                {result.removed_files === 1 ? "" : "s"}.
              </p>
            </div>
          ) : null}
        </div>
      ) : (
        <EmptyPanel label="A revert checkpoint will be available after a run starts." />
      )}
    </Panel>
  );
}

function PrSummaryPanel({ run }: { run: RunResponse | null }) {
  const [copied, setCopied] = useState(false);
  const reviewTitle = run ? getReviewTitle(run) : "";
  const verificationText = run
    ? `${run.tests.command} ${run.tests.status}`
    : "";
  const markdown = run ? run.pr_summary.markdown ?? buildPrMarkdown(run) : "";

  async function copyMarkdown() {
    if (!markdown) {
      return;
    }

    try {
      await navigator.clipboard.writeText(markdown);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }

  return (
    <Panel title="PR Summary">
      {run ? (
        <div className="grid gap-5 lg:grid-cols-[0.92fr_1.08fr]">
          <div className="rounded-[8px] border border-white/10 bg-[#111214] p-5 text-zinc-50">
            <p className="text-xs font-medium uppercase text-zinc-500">
              Given task
            </p>
            <h2 className="mt-3 text-lg font-semibold leading-snug text-zinc-50">
              {reviewTitle}
            </h2>
            <div className="mt-5 grid gap-2 sm:grid-cols-2">
              <span className="rounded-[6px] bg-emerald-400/10 px-3 py-2 text-center text-xs font-medium text-emerald-300 ring-1 ring-emerald-400/20">
                {verificationText}
              </span>
              <span className="rounded-[6px] bg-[#18191b] px-3 py-2 text-center text-xs font-medium text-zinc-300 border border-white/10">
                Human review required
              </span>
            </div>
          </div>
          <div className="rounded-[8px] border border-white/10 bg-[#111214] p-5">
            <p className="text-xs font-medium uppercase text-zinc-500">
              Review notes
            </p>
            <div className="mt-4 grid gap-3">
              {run.pr_summary.body.map((item) => (
                <div
                  className="grid grid-cols-[8px_minmax(0,1fr)] gap-3 text-sm leading-6 text-zinc-300"
                  key={item}
                >
                  <span className="mt-2 size-1.5 rounded-full bg-[#0099ff]" />
                  <span>{item}</span>
                </div>
              ))}
              <div className="grid grid-cols-[8px_minmax(0,1fr)] gap-3 text-sm leading-6 text-zinc-300">
                <span className="mt-2 size-1.5 rounded-full bg-zinc-500" />
                <span>No commit, push, or merge was performed automatically.</span>
              </div>
            </div>
            <div className="mt-5 rounded-[8px] bg-[#18191b] p-3 font-mono text-xs text-zinc-400 border border-white/10">
              {run.changed_files.length} changed file
              {run.changed_files.length === 1 ? "" : "s"} ready for review
            </div>
          </div>
          <div className="lg:col-span-2 rounded-[8px] border border-white/10 bg-[#111214] p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-medium uppercase text-zinc-500">
                  Copy-ready markdown
                </p>
                <p className="mt-2 text-sm text-zinc-300">
                  Prepared for a draft PR body or review comment.
                </p>
              </div>
              <button
                className="rounded-[6px] bg-[#18191b] px-4 py-2 text-xs font-medium text-zinc-300 ring-1 ring-white/10 transition hover:bg-[#18191b] hover:text-zinc-50"
                onClick={copyMarkdown}
                type="button"
              >
                {copied ? "Copied" : "Copy markdown"}
              </button>
            </div>
            <pre className="mt-4 max-h-56 overflow-auto whitespace-pre-wrap rounded-[6px] bg-[#18191b] p-4 font-mono text-xs leading-5 text-zinc-300 border border-white/10">
              {markdown}
            </pre>
          </div>
        </div>
      ) : (
        <EmptyPanel label="The generated PR title and summary will be shown after Code Pilot completes." />
      )}
    </Panel>
  );
}

function RevertConfirmDialog({
  run,
  isOpen,
  isReverting,
  onCancel,
  onConfirm,
}: {
  run: RunResponse | null;
  isOpen: boolean;
  isReverting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  if (!isOpen || !run) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 px-4 backdrop-blur-sm">
      <section className="w-full max-w-lg rounded-[10px] border border-white/10 bg-[#101010] p-6 shadow-[0_24px_80px_rgba(0,0,0,0.55)]">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.08em] text-red-300">
              Local checkpoint restore
            </p>
            <h2 className="mt-3 text-xl font-semibold text-zinc-50">
              Revert this run?
            </h2>
          </div>
          <StatusPill value={run.status} />
        </div>
        <p className="mt-4 text-sm leading-6 text-zinc-300">
          Code Pilot will restore the target repo to the checkpoint captured
          immediately before run <span className="font-mono">{run.run_id}</span>.
          Changes from this run will be removed, while earlier local work stays
          in place.
        </p>
        <div className="mt-5 rounded-[8px] border border-white/10 bg-[#18191b] p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.08em] text-zinc-500">
            Run artifact remains
          </p>
          <p className="mt-2 text-sm leading-6 text-zinc-300">
            The flight recorder and diff stay visible as historical evidence,
            but the working tree is restored locally.
          </p>
        </div>
        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button
            className="inline-flex min-h-10 items-center justify-center rounded-md border border-white/10 bg-[#18191b] px-4 text-sm font-semibold text-zinc-300 transition hover:text-zinc-50"
            disabled={isReverting}
            onClick={onCancel}
            type="button"
          >
            Cancel
          </button>
          <button
            className="inline-flex min-h-10 items-center justify-center rounded-md border border-red-400/20 bg-red-400/10 px-4 text-sm font-semibold text-red-100 transition hover:bg-red-400/15 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isReverting}
            onClick={onConfirm}
            type="button"
          >
            {isReverting ? "Restoring..." : "Revert run"}
          </button>
        </div>
      </section>
    </div>
  );
}

function DiffViewer({
  file,
  onClose,
  task,
}: {
  file: ChangedFile | null;
  onClose: () => void;
  task: string;
}) {
  const [summaries, setSummaries] = useState<Record<string, string>>({});
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [loadingPath, setLoadingPath] = useState<string | null>(null);

  if (!file) {
    return null;
  }

  const reviewSummary = summaries[file.path];
  const isReviewLoading = loadingPath === file.path;
  const diff = buildLineDiff(
    file.before_contents ?? "",
    file.after_contents ?? "",
  );

  async function generateReviewSummary() {
    if (!file) {
      return;
    }

    setReviewError(null);
    setLoadingPath(file.path);

    try {
      const response = await fetch(REVIEW_API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          path: file.path,
          task,
          before_contents: file.before_contents ?? "",
          after_contents: file.after_contents ?? "",
        }),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail ?? "Review assistant failed.");
      }

      setSummaries((current) => ({
        ...current,
        [file.path]: payload.summary,
      }));
    } catch (error) {
      setReviewError(
        error instanceof Error
          ? error.message
          : "Review assistant failed.",
      );
    } finally {
      setLoadingPath(null);
    }
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/80 p-4 backdrop-blur-sm">
      <section className="flex max-h-[92vh] w-full max-w-6xl flex-col rounded-[10px] bg-[#101010] shadow-[0_24px_80px_rgba(0,0,0,0.55)] ring-1 ring-white/15">
        <div className="flex min-w-0 items-start justify-between gap-4 border-b border-white/10 p-4">
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase text-zinc-500">
              File diff
            </p>
            <h3 className="mt-2 break-all font-mono text-base font-semibold text-zinc-50">
              {file.path}
            </h3>
          </div>
          <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
            <button
              className="rounded-[6px] bg-[#18191b] px-3 py-2 text-xs font-medium text-zinc-300 ring-1 ring-white/10 transition hover:bg-[#18191b] hover:text-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isReviewLoading}
              onClick={generateReviewSummary}
              type="button"
            >
              {isReviewLoading
                ? "Reviewing..."
                : reviewSummary
                  ? "Regenerate review"
                  : "Review assistant"}
            </button>
            <button
              className="rounded-[6px] bg-[#18191b] px-3 py-2 text-xs font-medium text-zinc-300 border border-white/10 transition hover:bg-[#222326] hover:text-zinc-50"
              onClick={onClose}
              type="button"
            >
              Back to Code Pilot
            </button>
          </div>
        </div>

        {reviewSummary || reviewError ? (
          <div className="border-b border-white/10 bg-[#0c1217] px-4 py-3">
            <p className="text-xs font-medium uppercase text-zinc-300">
              Review Assistant
            </p>
            {reviewSummary ? (
              <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-zinc-300">
                {reviewSummary}
              </p>
            ) : null}
            {reviewError ? (
              <p className="mt-2 text-sm leading-6 text-red-300">
                {reviewError}
              </p>
            ) : null}
          </div>
        ) : null}

        <div className="grid min-h-0 flex-1 gap-px overflow-hidden bg-[#18191b] md:grid-cols-2">
          <CodePane
            label="Before HEAD"
            lines={diff.before}
          />
          <CodePane
            label="After working tree"
            lines={diff.after}
          />
        </div>

        {file.content_truncated ? (
          <p className="border-t border-white/10 px-4 py-3 text-xs text-amber-200">
            Large file content was truncated for display.
          </p>
        ) : null}
      </section>
    </div>
  );
}

function CodePane({
  label,
  lines,
}: {
  label: string;
  lines: DiffLine[];
}) {
  return (
    <div className="min-h-0 bg-[#141414]">
      <div className="border-b border-white/10 px-4 py-3 text-xs font-medium uppercase text-zinc-500">
        {label}
      </div>
      <div className="max-h-[70vh] min-h-[320px] overflow-auto p-3 font-mono text-xs leading-5">
        {lines.length ? (
          lines.map((line, index) => (
            <div
              className={`grid grid-cols-[30px_24px_minmax(0,1fr)] gap-2 rounded-[3px] px-2 py-0.5 ${diffLineTone(
                line.type,
              )}`}
              key={`${label}-${index}`}
            >
              <span className="select-none text-right text-zinc-400">
                {line.lineNumber || ""}
              </span>
              <span className="select-none text-center font-semibold">
                {line.marker}
              </span>
              <span className="min-w-0 whitespace-pre-wrap break-words">
                {line.value || " "}
              </span>
            </div>
          ))
        ) : (
          <div className="rounded-[6px] border border-white/10 bg-[#111214] p-3 text-zinc-500">
            No file content captured.
          </div>
        )}
      </div>
    </div>
  );
}

type DiffLineType = "added" | "removed" | "unchanged" | "empty";

type DiffLine = {
  type: DiffLineType;
  marker: "+" | "-" | " ";
  value: string;
  lineNumber?: number;
};

function buildLineDiff(beforeValue: string, afterValue: string) {
  const beforeLines = splitLines(beforeValue);
  const afterLines = splitLines(afterValue);
  const table = buildLcsTable(beforeLines, afterLines);
  const before: DiffLine[] = [];
  const after: DiffLine[] = [];
  let beforeIndex = 0;
  let afterIndex = 0;

  while (beforeIndex < beforeLines.length || afterIndex < afterLines.length) {
    if (
      beforeIndex < beforeLines.length &&
      afterIndex < afterLines.length &&
      beforeLines[beforeIndex] === afterLines[afterIndex]
    ) {
      before.push({
        type: "unchanged",
        marker: " ",
        value: beforeLines[beforeIndex],
        lineNumber: beforeIndex + 1,
      });
      after.push({
        type: "unchanged",
        marker: " ",
        value: afterLines[afterIndex],
        lineNumber: afterIndex + 1,
      });
      beforeIndex += 1;
      afterIndex += 1;
      continue;
    }

    const shouldAdd =
      afterIndex < afterLines.length &&
      (beforeIndex === beforeLines.length ||
        table[beforeIndex][afterIndex + 1] >= table[beforeIndex + 1][afterIndex]);

    if (shouldAdd) {
      before.push({
        type: "empty",
        marker: " ",
        value: "",
      });
      after.push({
        type: "added",
        marker: "+",
        value: afterLines[afterIndex],
        lineNumber: afterIndex + 1,
      });
      afterIndex += 1;
      continue;
    }

    before.push({
      type: "removed",
      marker: "-",
      value: beforeLines[beforeIndex],
      lineNumber: beforeIndex + 1,
    });
    after.push({
      type: "empty",
      marker: " ",
      value: "",
    });
    beforeIndex += 1;
  }

  return { before, after };
}

function splitLines(value: string) {
  if (!value) {
    return [];
  }

  return value.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n");
}

function buildLcsTable(beforeLines: string[], afterLines: string[]) {
  const table = Array.from({ length: beforeLines.length + 1 }, () =>
    Array.from({ length: afterLines.length + 1 }, () => 0),
  );

  for (let beforeIndex = beforeLines.length - 1; beforeIndex >= 0; beforeIndex -= 1) {
    for (let afterIndex = afterLines.length - 1; afterIndex >= 0; afterIndex -= 1) {
      table[beforeIndex][afterIndex] =
        beforeLines[beforeIndex] === afterLines[afterIndex]
          ? table[beforeIndex + 1][afterIndex + 1] + 1
          : Math.max(
              table[beforeIndex + 1][afterIndex],
              table[beforeIndex][afterIndex + 1],
            );
    }
  }

  return table;
}

function diffLineTone(type: DiffLineType) {
  if (type === "added") {
    return "bg-emerald-400/10 text-emerald-100";
  }

  if (type === "removed") {
    return "bg-red-400/10 text-red-100";
  }

  if (type === "empty") {
    return "bg-black/20 text-zinc-300";
  }

  return "text-zinc-300";
}

function MemoryColumn({
  title,
  description,
  items,
  expandedItems,
  expandedLabel = "Show more",
  featured = false,
}: {
  title: string;
  description: string;
  items: string[];
  expandedItems?: string[];
  expandedLabel?: string;
  featured?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const visibleItems = expanded && expandedItems ? expandedItems : items;
  const canExpand = Boolean(expandedItems && expandedItems.length > items.length);

  return (
    <article
      className={`rounded-[4px] p-4 ring-1 ${
        featured
          ? "border border-white/10 bg-[#09090a] text-zinc-100"
          : "border border-white/10 bg-[#101113] text-zinc-50"
      }`}
    >
      <h3 className="text-base font-semibold text-zinc-50">
        {title}
      </h3>
      <p className="mt-1 text-xs leading-5 text-zinc-400">{description}</p>
      {items.length > 0 ? (
        <>
          <ul className="mt-4 grid gap-2.5">
            {visibleItems.map((item) => (
              <li
                className="flex gap-2 rounded-md border border-white/10 bg-[#111214] px-3 py-2 text-sm leading-6 text-zinc-300"
                key={item}
              >
                <span className="mt-2 size-1.5 shrink-0 rounded-full bg-zinc-400" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
          {canExpand ? (
            <button
              className="mt-4 inline-flex items-center gap-2 rounded-md border border-white/10 bg-[#111214] px-3 py-2 text-xs font-medium text-zinc-300 transition hover:bg-[#18191b] hover:text-zinc-50"
              onClick={() => setExpanded((current) => !current)}
              type="button"
            >
              {expanded ? "Show curated memory" : expandedLabel}
              <ChevronIcon open={expanded} />
            </button>
          ) : null}
        </>
      ) : (
        <p
          className="mt-4 text-sm leading-6 text-zinc-300"
        >
          No memory used on this run.
        </p>
      )}
    </article>
  );
}

function getAgentHighlights(agent: AgentStep, run: RunResponse) {
  if (agent.name === "Coder Agent") {
    const fileNames = run.changed_files.map((file) => file.path).join(", ");
    const highlights = [
      "Scoped SDK read/write tools",
      `Changed ${run.changed_files.length} file${
        run.changed_files.length === 1 ? "" : "s"
      }`,
      fileNames ? `${fileNames} updated` : "No code changes captured",
    ];

    if (/test repair/i.test(agent.details)) {
      highlights.push(
        run.tests.status === "passed"
          ? "Pytest failed, repair passed"
          : "Pytest repair attempted",
      );
    }

    return highlights;
  }

  if (agent.name === "Repair Agent") {
    return [
      "Focused pytest repair pass",
      `${run.changed_files.length} files after repair`,
    ];
  }

  if (agent.name === "Tester Agent") {
    const summary = parseTestSummary(run);
    return [`${run.tests.command} ${run.tests.status}`, summary.label];
  }

  if (agent.name === "Reviewer Agent") {
    return [
      `${run.changed_files.length} files ready for review`,
      "Human review required before merge",
    ];
  }

  if (agent.name === "Planner Agent") {
    const model = agent.details.match(/Selected model:\s*([^\n]+)/)?.[1]?.trim();
    return [
      model ? `Selected ${model}` : "Selected coding model",
      "Scoped files and verification",
    ];
  }

  return [];
}

function parsePlannerLog(details: string) {
  const summary: string[] = [];
  const model: string[] = [];
  const plan: string[] = [];
  const context: string[] = [];
  const guardrails: string[] = [];
  const other: string[] = [];
  let section: "summary" | "plan" | "context" | "guardrails" | "other" =
    "summary";

  for (const rawLine of details.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) {
      continue;
    }

    if (line === "Structured plan") {
      section = "plan";
      continue;
    }

    if (line === "Context sent to Code Pilot") {
      section = "context";
      continue;
    }

    if (line.startsWith("Selected model:")) {
      model.push(cleanLogLine(line.replace(/^Selected model:\s*/, "")));
      continue;
    }

    if (line.startsWith("Guardrails:")) {
      section = "guardrails";
      guardrails.push(cleanLogLine(line.replace(/^Guardrails:\s*/, "")));
      continue;
    }

    if (section === "summary") {
      summary.push(cleanLogLine(line));
    } else if (section === "plan") {
      plan.push(cleanLogLine(line.replace(/^-\s*/, "")));
    } else if (section === "context") {
      context.push(cleanLogLine(line.replace(/^-\s*/, "")));
    } else if (section === "guardrails") {
      guardrails.push(cleanLogLine(line));
    } else {
      other.push(cleanLogLine(line));
    }
  }

  return {
    summary: summary.slice(0, 4),
    model: model.length
      ? [...model, modelRoutingHint(model[0])]
      : ["Model selection not captured"],
    plan,
    context,
    guardrails,
    other: other.slice(0, 8),
  };
}

function modelRoutingHint(model: string) {
  const normalized = model.toLowerCase();

  if (normalized.includes("luna")) {
    return "Small endpoint/test task -> Luna";
  }

  if (normalized.includes("sol")) {
    return "Complex refactor/auth/security task -> Sol";
  }

  if (normalized.includes("terra")) {
    return "Balanced feature work -> Terra";
  }

  return "Planner selected the model based on task complexity.";
}

function parseCoderLog(details: string) {
  const setup: string[] = [];
  const repair: string[] = [];
  const tools: string[] = [];
  const assistant: string[] = [];
  const other: string[] = [];
  let currentAttempt: "primary" | "repair" = "primary";

  for (const rawLine of details.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) {
      continue;
    }

    if (
      line.startsWith("BroPilot backend verification failed") ||
      line.startsWith("Test repair") ||
      line.startsWith("After repair")
    ) {
      repair.push(cleanLogLine(line));
      continue;
    }

    if (line.startsWith("attempt: test-repair")) {
      currentAttempt = "repair";
      repair.push(cleanLogLine(line));
      continue;
    }

    if (line.startsWith("attempt: primary")) {
      currentAttempt = "primary";
      setup.push(cleanLogLine(line));
      continue;
    }

    if (
      line.startsWith("First OpenAI Agents SDK") ||
      line.startsWith("Fallback") ||
      line.startsWith("Temporary") ||
      line.startsWith("command:") ||
      line.startsWith("return_code:") ||
      line.startsWith("runner_status:") ||
      line.startsWith("system/")
    ) {
      if (currentAttempt === "repair") {
        repair.push(cleanLogLine(line));
      } else {
        setup.push(cleanLogLine(line));
      }
      continue;
    }

    if (line.startsWith("tool_use:") || line.startsWith("tool_result")) {
      tools.push(cleanLogLine(line));
      continue;
    }

    if (line.startsWith("assistant:")) {
      const note = cleanLogLine(line.replace(/^assistant:\s*/, ""));
      if (note) {
        assistant.push(note);
      }
      continue;
    }

    if (line === "stdout:" || line === "stderr:") {
      continue;
    }

    other.push(cleanLogLine(line));
  }

  return {
    setup,
    repair,
    tools: tools.slice(0, 8),
    assistant: assistant.slice(0, 4),
    other: other.slice(0, 6),
  };
}

function cleanLogLine(line: string) {
  const compacted = line.startsWith("command:")
    ? line
    : line.replace(/\\n/g, " ");

  return compacted.replace(/\s+/g, " ").replace(/\\"/g, '"').slice(0, 420);
}

function parseTestSummary(run: RunResponse) {
  const log = getTesterLog(run);
  const passMatch = log.match(/(\d+)\s+passed/);
  const collectedMatch = log.match(/collected\s+(\d+)\s+items?/);

  if (passMatch) {
    const collected = collectedMatch?.[1] ?? passMatch[1];
    return {
      label: `${passMatch[1]} passed / ${collected} collected`,
    };
  }

  if (/SyntaxError: 'await' outside async function/.test(log)) {
    return {
      label: "Pytest collection failed: async middleware needs an async function.",
    };
  }

  if (/ERROR collecting/.test(log) || /error during collection/i.test(log)) {
    const errorFile = log.match(/ERROR collecting\s+([^\s]+)/);
    return {
      label: errorFile
        ? `Pytest collection failed in ${errorFile[1].trim()}.`
        : "Pytest collection failed before tests could run.",
    };
  }

  const failedMatch = log.match(/(\d+)\s+failed/);
  if (failedMatch) {
    return {
      label: `${failedMatch[1]} test${failedMatch[1] === "1" ? "" : "s"} failed.`,
    };
  }

  return {
    label:
      cleanStatusSummary(run.tests.summary) || "Verification output captured.",
  };
}

function cleanStatusSummary(summary: string) {
  return summary
    .replace(/!/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function getTesterLog(run: RunResponse) {
  const tester = run.agents.find((agent) => agent.name === "Tester Agent");
  return tester?.details || run.tests.summary;
}

function friendlyMemoryItems(items: string[]) {
  return items.map((item) =>
    item === "No persisted repo-specific memory store is enabled yet."
      ? "No prior repo memory loaded for this run."
      : item,
  );
}

function parseGitStatusRows(details: string) {
  return details
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter(Boolean)
    .map((line) => {
      if (line === "Working tree was clean.") {
        return {
          status: "clean",
          path: line,
        };
      }

      const status = line.slice(0, 2).trim() || "changed";
      const path = line.slice(2).trim() || line.trim();

      return {
        status,
        path,
      };
    });
}

function buildMemoryDisplay(memory: MemoryReport) {
  const beforeAll = uniqueItems(friendlyMemoryItems(memory.before));
  const before = compactBeforeMemory(beforeAll);
  const learnedRaw = uniqueItems(memory.learned);
  const beforeKeys = new Set(before.map(normalizeMemoryKey));
  const learnedNew = learnedRaw.filter(
    (item) => !beforeKeys.has(normalizeMemoryKey(item)),
  );
  const used = compactUsedMemory(memory.used);

  return {
    before,
    beforeAll,
    learned: learnedNew.length ? learnedNew : ["No new repo memory was added."],
    used,
  };
}

function compactUsedMemory(items: string[]) {
  const unique = uniqueItems(items);
  const operational = unique.filter(
    (item) =>
      item.includes("Loaded ") ||
      item.includes("guardrails") ||
      item.includes("Backend subprocess"),
  );
  const featureLessons = unique
    .filter((item) => item.startsWith("Feature:"))
    .slice(0, 4)
    .map((item) => `Feature lesson: ${item}`);
  const examples = unique
    .filter(
      (item) =>
        !operational.includes(item) &&
        !item.startsWith("Feature:"),
    )
    .slice(0, 3)
    .map((item) => `Memory hint: ${item}`);

  return [...operational, ...featureLessons, ...examples];
}

function compactBeforeMemory(items: string[]) {
  const unique = uniqueItems(items);
  const verificationNotes = unique.filter((item) =>
    item.startsWith("Last verification"),
  );
  const latestPassed =
    verificationNotes.find((item) => item.includes("passed")) ?? null;
  const latestVerification =
    latestPassed ?? verificationNotes[verificationNotes.length - 1] ?? null;
  const stableFacts = unique
    .filter(
      (item) =>
        !item.startsWith("Last verification") &&
        !item.startsWith("Recent BroPilot changes touched"),
    )
    .slice(0, 4);

  return latestVerification
    ? [...stableFacts, latestVerification]
    : stableFacts.slice(0, 5);
}

function uniqueItems(items: string[]) {
  const seen = new Set<string>();
  const result: string[] = [];

  for (const item of items) {
    const cleaned = item.trim();
    const key = normalizeMemoryKey(cleaned);

    if (!cleaned || seen.has(key)) {
      continue;
    }

    seen.add(key);
    result.push(cleaned);
  }

  return result;
}

function normalizeMemoryKey(item: string) {
  return item.toLowerCase().replace(/\s+/g, " ");
}

function getReviewTitle(run: RunResponse) {
  const title = run.pr_summary.title.trim();
  const task = run.task.trim();

  if (!title) {
    return task || "Code Pilot code changes";
  }

  if (task.startsWith(title) && title.length < task.length) {
    return task;
  }

  return title;
}

function buildPrMarkdown(run: RunResponse) {
  const changedFiles = run.changed_files.map((file) => `  - ${file.path}`);
  const changedSection = changedFiles.length
    ? ["- Changed files:", ...changedFiles]
    : ["- No code changes were captured."];

  return [
    "## Summary",
    `- Task: ${run.task}`,
    ...changedSection,
    "",
    "## Verification",
    `- ${run.tests.command} ${run.tests.status}`,
    "",
    "## Review",
    "- Human review required before merge",
    "- No automatic commit, push, or merge was performed",
  ].join("\n");
}

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Not captured";
  }

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}





