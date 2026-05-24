"use client";

import type { FormEvent, ReactNode } from "react";
import { useMemo, useState } from "react";

const API_URL = "http://127.0.0.1:8000/api/runs/start";
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

const statusTone: Record<string, string> = {
  completed: "bg-emerald-400/10 text-emerald-300 ring-emerald-400/20",
  passed: "bg-emerald-400/10 text-emerald-300 ring-emerald-400/20",
  running: "bg-[#0099ff]/10 text-[#8fd0ff] ring-[#0099ff]/25",
  failed: "bg-red-400/10 text-red-300 ring-red-400/20",
  blocked: "bg-orange-400/10 text-orange-300 ring-orange-400/20",
  needs_attention: "bg-amber-400/10 text-amber-200 ring-amber-400/25",
  skipped: "bg-white/10 text-zinc-300 ring-white/15",
  low: "bg-emerald-400/10 text-emerald-300 ring-emerald-400/20",
  medium: "bg-amber-400/10 text-amber-200 ring-amber-400/25",
  high: "bg-red-400/10 text-red-300 ring-red-400/20",
};

function getStatusTone(status: string) {
  return (
    statusTone[status.toLowerCase()] ?? "bg-white/10 text-zinc-300 ring-white/15"
  );
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
      className={`size-2.5 shrink-0 border-b border-r border-[#8fd0ff] transition-transform ${
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
      className={`min-w-0 rounded-[10px] bg-[#141414] p-5 shadow-[0_18px_60px_rgba(0,0,0,0.28)] ring-1 ring-white/10 ${className}`}
    >
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          {eyebrow ? (
            <p className="mb-2 text-xs font-medium uppercase text-zinc-500">
              {eyebrow}
            </p>
          ) : null}
          <h2 className="text-xl font-semibold text-white">{title}</h2>
        </div>
      </div>
      {children}
    </section>
  );
}

function EmptyPanel({ label }: { label: string }) {
  return (
    <div className="rounded-[8px] border border-dashed border-white/10 bg-black/20 p-5 text-sm text-zinc-500">
      {label}
    </div>
  );
}

function WorkflowSteps() {
  const steps = [
    "Provide repository",
    "Gitclaw SDK",
    "Code changes",
    "Pytest",
    "Review summary",
  ];

  return (
    <section className="rounded-[10px] bg-[#101010] p-4 ring-1 ring-[#0099ff]/20 shadow-[0_0_60px_rgba(0,153,255,0.08)]">
      <div className="flex flex-wrap items-center justify-center gap-2">
        {steps.map((step, index) => (
          <div className="flex items-center gap-2" key={step}>
            <span className="rounded-[6px] bg-[#071521] px-3 py-2 text-xs font-medium text-[#8fd0ff] ring-1 ring-[#0099ff]/35 shadow-[0_0_24px_rgba(0,153,255,0.14)]">
              {step}
            </span>
            {index < steps.length - 1 ? (
              <span className="text-xs text-[#0099ff]/60">-&gt;</span>
            ) : null}
          </div>
        ))}
      </div>
    </section>
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

  const testSummary = run ? parseTestSummary(run) : null;

  return (
    <main className="min-h-screen bg-[#090909] text-white">
      <div className="mx-auto flex w-full max-w-[1199px] flex-col gap-6 px-5 py-6 sm:px-8 lg:px-10">
        <header className="flex min-h-14 items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="grid size-10 place-items-center rounded-full bg-white text-sm font-bold text-black">
              BP
            </div>
            <div>
              <p className="text-sm font-semibold text-white">BroPilot</p>
              <p className="text-xs text-zinc-500">Safe PR builder</p>
            </div>
          </div>
          <div className="hidden items-center gap-2 rounded-full bg-[#141414] px-4 py-2 text-xs text-zinc-300 ring-1 ring-white/10 sm:flex">
            <span className="size-2 rounded-full bg-emerald-400 shadow-[0_0_16px_rgba(52,211,153,0.8)]" />
            SDK runner connected
          </div>
        </header>

        <section className="mx-auto max-w-3xl py-4 text-center">
          <h1 className="bg-[linear-gradient(90deg,#ffffff_0%,#0099ff_34%,#ffffff_58%,#d44df0_82%,#ff7a3d_100%)] bg-clip-text text-5xl font-semibold leading-none text-transparent drop-shadow-[0_0_42px_rgba(0,153,255,0.38)] sm:text-6xl lg:text-7xl">
            BroPilot
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg leading-7 text-zinc-400 sm:text-xl">
            Your repo&apos;s AI teammate for safe, reviewable code changes.
          </p>
        </section>

        <WorkflowSteps />

        <section className="grid min-w-0 gap-6 lg:grid-cols-[minmax(0,1.06fr)_minmax(380px,0.94fr)]">
          <div className="min-w-0 rounded-[10px] bg-[#141414] p-6 ring-1 ring-white/10 sm:p-8">
            <form className="grid gap-4" onSubmit={startRun}>
              <label className="grid gap-2">
                <span className="text-sm font-medium text-zinc-300">
                  Repo path
                </span>
                <input
                  className="min-h-12 rounded-[10px] bg-[#1c1c1c] px-4 text-sm text-white outline-none ring-1 ring-white/10 transition focus:ring-[#0099ff]/70"
                  value={repoPath}
                  onChange={(event) => setRepoPath(event.target.value)}
                  placeholder="D:\\bropilot-demo"
                  required
                />
              </label>

              <label className="grid gap-2">
                <span className="text-sm font-medium text-zinc-300">Task</span>
                <textarea
                  className="min-h-32 resize-y rounded-[10px] bg-[#1c1c1c] px-4 py-3 text-sm leading-6 text-white outline-none ring-1 ring-white/10 transition focus:ring-[#0099ff]/70"
                  value={task}
                  onChange={(event) => setTask(event.target.value)}
                  placeholder="Describe the code change BroPilot should prepare"
                  required
                />
              </label>

              <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                <button
                  className="inline-flex min-h-11 items-center justify-center rounded-full bg-white px-4 text-sm font-semibold text-black transition hover:bg-zinc-200 disabled:cursor-not-allowed disabled:bg-zinc-500 disabled:text-zinc-900"
                  disabled={isLoading}
                  type="submit"
                >
                  {isLoading ? "Running BroPilot..." : "Run BroPilot"}
                </button>
                {error ? (
                  <p className="rounded-[10px] bg-red-400/10 px-4 py-3 text-sm text-red-200 ring-1 ring-red-400/20">
                    {error}
                  </p>
                ) : null}
              </div>
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
          <ChangedFilesPanel run={run} onOpenDiff={setDiffFile} />
          <Panel title="Test Results">
            {run && testSummary ? (
              <div className="rounded-[8px] bg-[#1c1c1c] p-4 ring-1 ring-white/10">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="text-sm font-semibold text-white">
                      {run.tests.command} {run.tests.status}
                    </p>
                    <p className="mt-2 text-sm text-zinc-400">
                      {testSummary.label}
                    </p>
                  </div>
                  <StatusPill value={run.tests.status} />
                </div>
                <button
                  className="mt-4 inline-flex items-center gap-2 rounded-[6px] bg-black/30 px-3 py-2 text-xs font-medium text-zinc-300 ring-1 ring-white/10 transition hover:text-white"
                  onClick={() => setShowTestLog((current) => !current)}
                  type="button"
                >
                  <span>{showTestLog ? "Hide test log" : "Show test log"}</span>
                  <ChevronIcon open={showTestLog} />
                </button>
                {showTestLog ? (
                  <pre className="mt-3 max-h-56 w-full max-w-full overflow-auto whitespace-pre-wrap break-words rounded-[10px] bg-black/45 p-3 font-mono text-xs leading-5 text-zinc-300 ring-1 ring-white/10">
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
                <div className="rounded-[8px] bg-[#1c1c1c] p-4 ring-1 ring-white/10">
                  <p className="text-sm text-zinc-500">Risk score</p>
                  <div className="mt-3">
                    <StatusPill value={run.safety.risk_score} />
                  </div>
                </div>
                <div className="grid gap-3">
                  {run.safety.blocked_actions.map((action) => (
                    <article
                      className="rounded-[8px] bg-orange-400/10 p-4 ring-1 ring-orange-300/15"
                      key={action.command}
                    >
                      <code className="font-mono text-sm text-orange-100">
                        {action.command}
                      </code>
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

          <Panel
            title="Memory Panel"
          >
            {run ? (
              <div className="grid gap-4 md:grid-cols-3">
                {(() => {
                  const memory = buildMemoryDisplay(run.memory);

                  return (
                    <>
                      <MemoryColumn title="Before" items={memory.before} />
                      <MemoryColumn
                        title="Learned"
                        items={memory.learned}
                        featured
                      />
                      <MemoryColumn title="Used" items={memory.used} />
                    </>
                  );
                })()}
              </div>
            ) : (
              <EmptyPanel label="BroPilot memory will grow from each reviewed run." />
            )}
          </Panel>
        </section>

        <PrSummaryPanel run={run} />
        <DiffViewer file={diffFile} onClose={() => setDiffFile(null)} />
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
    <div className="min-w-0 rounded-[10px] bg-[#141414] p-6 ring-1 ring-white/10 sm:p-8">
      <div className="flex h-full flex-col justify-between">
        <div>
          <p className="mb-4 text-sm font-medium text-zinc-300">Current run</p>
          {run ? (
            <>
              <div className="mb-4 flex flex-wrap items-center gap-2">
                <StatusPill value={run.status} />
                <span className="rounded-full bg-white/10 px-3 py-1.5 text-xs text-zinc-300 ring-1 ring-white/10">
                  CLI disabled
                </span>
                <span className="rounded-full bg-white/10 px-3 py-1.5 text-xs text-zinc-300 ring-1 ring-white/10">
                  Human review required
                </span>
              </div>
              <div className="rounded-[8px] bg-white/10 p-4 ring-1 ring-white/10">
                <p className="text-xs font-medium uppercase text-zinc-500">
                  Task
                </p>
                <p className="mt-3 text-sm font-medium leading-6 text-zinc-200">
                  {run.task}
                </p>
              </div>
            </>
          ) : (
            <>
              <h2 className="text-3xl font-semibold leading-tight text-white">
                Ready to launch the flight recorder.
              </h2>
              <p className="mt-4 text-sm leading-6 text-zinc-400">
                Submit the demo task to watch Gitclaw edit, BroPilot verify, and
                the dashboard package the result for review.
              </p>
            </>
          )}
        </div>

        <div className="mt-8 grid grid-cols-2 gap-3 xl:grid-cols-3">
          {runMeta ? (
            runMeta.map((item) => (
              <div
                className="rounded-[6px] bg-[#1c1c1c] p-4 ring-1 ring-white/10"
                key={item.label}
              >
                <p className="text-xs text-zinc-500">{item.label}</p>
                <p className="mt-2 break-words text-sm font-medium text-white">
                  {item.value}
                </p>
              </div>
            ))
          ) : (
            <>
              <div className="rounded-[6px] bg-[#1c1c1c] p-4 ring-1 ring-white/10">
                <p className="text-xs text-zinc-500">Workflow</p>
                <p className="mt-2 text-sm font-medium text-white">5 agents</p>
              </div>
              <div className="rounded-[6px] bg-[#1c1c1c] p-4 ring-1 ring-white/10">
                <p className="text-xs text-zinc-500">Runner</p>
                <p className="mt-2 text-sm font-medium text-white">
                  Gitclaw SDK
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
        <div className="grid size-12 shrink-0 place-items-center rounded-full bg-white text-sm font-semibold text-black">
          {index + 1}
        </div>
        {!isLast ? (
          <div className="hidden h-full min-h-12 w-px bg-white/10 sm:block" />
        ) : null}
      </div>
      <article className="min-w-0 rounded-[8px] bg-[#1c1c1c] p-4 ring-1 ring-white/10">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h3 className="text-base font-semibold text-white">{agent.name}</h3>
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
                className="rounded-[6px] bg-black/25 px-3 py-2 text-sm text-zinc-300 ring-1 ring-white/10"
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
              className="mt-4 inline-flex items-center gap-2 rounded-[6px] bg-black/30 px-3 py-2 text-xs font-medium text-zinc-300 ring-1 ring-white/10 transition hover:text-white"
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
      <div className="mt-3 rounded-[10px] bg-black/45 p-3 ring-1 ring-white/10">
        <p className="text-xs font-semibold uppercase text-zinc-500">
          Git status before run
        </p>
        {rows.length ? (
          <div className="mt-3 grid gap-2">
            {rows.map((row) => (
              <div
                className="grid min-w-0 grid-cols-[42px_minmax(0,1fr)] items-center gap-3 rounded-[8px] bg-white/5 px-3 py-2"
                key={`${row.status}-${row.path}`}
              >
                <span className="inline-flex min-h-6 items-center justify-center rounded-[5px] bg-white/10 px-2 font-mono text-[11px] text-zinc-300">
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

  return (
    <pre className="mt-3 max-h-64 w-full max-w-full overflow-auto whitespace-pre-wrap break-words rounded-[10px] bg-black/45 p-3 font-mono text-xs leading-5 text-zinc-300 ring-1 ring-white/10">
      {agent.details}
    </pre>
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
    <div className="mt-3 grid gap-3 rounded-[10px] bg-black/45 p-3 ring-1 ring-white/10">
      <div>
        <p className="text-xs font-semibold uppercase text-zinc-500">
          Code changes
        </p>
        <div className="mt-3 grid gap-2">
          {run.changed_files.map((file) => (
            <div
              className="flex min-w-0 flex-wrap items-center gap-2 rounded-[8px] bg-white/5 px-3 py-2"
              key={file.path}
            >
              <span className="min-w-0 break-all font-mono text-xs font-semibold text-white">
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
            className={`min-w-0 rounded-[8px] bg-white/5 px-3 py-2 text-xs leading-5 text-zinc-300 ${
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
}: {
  run: RunResponse | null;
  onOpenDiff: (file: ChangedFile) => void;
}) {
  return (
    <Panel title="Changed Files">
      {run ? (
        run.changed_files.length ? (
          <div className="grid gap-3">
            {run.changed_files.map((file) => (
              <article
                className="rounded-[8px] bg-[#1c1c1c] p-4 ring-1 ring-white/10"
                key={file.path}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="break-all font-mono text-sm text-white">
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
                    className="ml-auto rounded-[6px] bg-[#071521] px-3 py-1.5 text-xs font-medium text-[#8fd0ff] ring-1 ring-[#0099ff]/30 transition hover:bg-[#0a2033] hover:text-white"
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

function PrSummaryPanel({ run }: { run: RunResponse | null }) {
  const reviewTitle = run ? getReviewTitle(run) : "";
  const verificationText = run
    ? `${run.tests.command} ${run.tests.status}`
    : "";

  return (
    <Panel title="PR Summary">
      {run ? (
        <div className="grid gap-5 lg:grid-cols-[0.92fr_1.08fr]">
          <div className="rounded-[8px] bg-[#1c1c1c] p-5 text-white ring-1 ring-white/10">
            <p className="text-xs font-medium uppercase text-zinc-500">
              Given task
            </p>
            <h2 className="mt-3 text-lg font-semibold leading-snug text-white">
              {reviewTitle}
            </h2>
            <div className="mt-5 grid gap-2 sm:grid-cols-2">
              <span className="rounded-[6px] bg-emerald-400/10 px-3 py-2 text-center text-xs font-medium text-emerald-300 ring-1 ring-emerald-400/20">
                {verificationText}
              </span>
              <span className="rounded-[6px] bg-white/10 px-3 py-2 text-center text-xs font-medium text-zinc-200 ring-1 ring-white/10">
                Human review required
              </span>
            </div>
          </div>
          <div className="rounded-[8px] bg-[#1c1c1c] p-5 ring-1 ring-white/10">
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
                <span className="mt-2 size-1.5 rounded-full bg-white" />
                <span>No commit, push, or merge was performed automatically.</span>
              </div>
            </div>
            <div className="mt-5 rounded-[8px] bg-black/30 p-3 font-mono text-xs text-zinc-400 ring-1 ring-white/10">
              {run.changed_files.length} changed file
              {run.changed_files.length === 1 ? "" : "s"} ready for review
            </div>
          </div>
        </div>
      ) : (
        <EmptyPanel label="The generated PR title and summary will be shown after BroPilot completes." />
      )}
    </Panel>
  );
}

function DiffViewer({
  file,
  onClose,
}: {
  file: ChangedFile | null;
  onClose: () => void;
}) {
  if (!file) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/80 p-4 backdrop-blur-sm">
      <section className="flex max-h-[92vh] w-full max-w-6xl flex-col rounded-[10px] bg-[#101010] shadow-[0_24px_80px_rgba(0,0,0,0.55)] ring-1 ring-white/15">
        <div className="flex min-w-0 items-start justify-between gap-4 border-b border-white/10 p-4">
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase text-zinc-500">
              File diff
            </p>
            <h3 className="mt-2 break-all font-mono text-base font-semibold text-white">
              {file.path}
            </h3>
          </div>
          <button
            className="rounded-[6px] bg-white/10 px-3 py-2 text-xs font-medium text-zinc-200 ring-1 ring-white/10 transition hover:bg-white/15 hover:text-white"
            onClick={onClose}
            type="button"
          >
            Close
          </button>
        </div>

        <div className="grid min-h-0 flex-1 gap-px overflow-hidden bg-white/10 md:grid-cols-2">
          <CodePane
            label="Before HEAD"
            lines={buildLineDiff(file.before_contents ?? "", file.after_contents ?? "").before}
          />
          <CodePane
            label="After working tree"
            lines={buildLineDiff(file.before_contents ?? "", file.after_contents ?? "").after}
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
              <span className="select-none text-right text-zinc-600">
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
          <div className="rounded-[6px] bg-white/5 p-3 text-zinc-500">
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
    return "bg-black/20 text-zinc-700";
  }

  return "text-zinc-300";
}

function MemoryColumn({
  title,
  items,
  featured = false,
}: {
  title: string;
  items: string[];
  featured?: boolean;
}) {
  return (
    <article
      className={`rounded-[4px] p-4 ring-1 ${
        featured
          ? "bg-[#1c1c1c] text-white ring-[#0099ff]/25"
          : "bg-[#1c1c1c] text-white ring-white/10"
      }`}
    >
      <h3 className="text-sm font-semibold text-white">
        {title}
      </h3>
      {items.length > 0 ? (
        <ul className="mt-4 grid gap-3">
          {items.map((item) => (
            <li
              className="text-sm leading-6 text-zinc-100"
              key={item}
            >
              {item}
            </li>
          ))}
        </ul>
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
      "SDK runner used with CLI disabled",
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
    return ["Known files preloaded", "Read/write tools preferred"];
  }

  return [];
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
      line.startsWith("First Gitclaw") ||
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
  const before = compactBeforeMemory(friendlyMemoryItems(memory.before));
  const learnedRaw = uniqueItems(memory.learned);
  const beforeKeys = new Set(before.map(normalizeMemoryKey));
  const learnedNew = learnedRaw.filter(
    (item) => !beforeKeys.has(normalizeMemoryKey(item)),
  );
  const used = compactUsedMemory(memory.used);

  return {
    before,
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
  const examples = unique
    .filter((item) => !operational.includes(item))
    .slice(0, 3)
    .map((item) => `Memory hint: ${item}`);

  return [...operational, ...examples];
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
  const repoFacts = unique.filter((item) => !item.startsWith("Last verification"));

  return latestVerification ? [...repoFacts, latestVerification] : repoFacts;
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
    return task || "BroPilot code changes";
  }

  if (task.startsWith(title) && title.length < task.length) {
    return task;
  }

  return title;
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
