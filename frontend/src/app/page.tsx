"use client";

import type { FormEvent, ReactNode } from "react";
import { useMemo, useState } from "react";

const API_URL = "http://127.0.0.1:8000/api/runs/start";
const DEFAULT_REPO_PATH = "D:\\bropilot-demo";
const DEFAULT_TASK = "Fix profile lookup to return 404 for unknown users and add tests";

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
      className={`rounded-[20px] bg-[#141414] p-5 shadow-[0_18px_60px_rgba(0,0,0,0.28)] ring-1 ring-white/10 ${className}`}
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
    <div className="rounded-[15px] border border-dashed border-white/10 bg-black/20 p-5 text-sm text-zinc-500">
      {label}
    </div>
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

  const runMeta = useMemo(() => {
    if (!run) {
      return null;
    }

    return [
      { label: "Run", value: run.run_id },
      { label: "Status", value: run.status.replace("_", " ") },
      { label: "Changed", value: `${run.changed_files.length} files` },
      { label: "Tests", value: run.tests.status },
    ];
  }, [run]);

  async function startRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoading(true);
    setError(null);
    setOpenAgentLogs({});
    setShowTestLog(false);

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

        <section className="grid gap-6 lg:grid-cols-[minmax(0,1.06fr)_minmax(380px,0.94fr)]">
          <div className="rounded-[30px] bg-[#141414] p-6 ring-1 ring-white/10 sm:p-8 lg:p-10">
            <div className="mb-8 max-w-3xl">
              <p className="mb-4 text-sm font-medium text-[#8fd0ff]">
                Gitclaw SDK {"->"} code changes {"->"} pytest {"->"} review
                summary
              </p>
              <h1 className="max-w-3xl text-5xl font-semibold leading-none text-white sm:text-6xl lg:text-7xl">
                BroPilot
              </h1>
              <p className="mt-5 max-w-2xl text-lg leading-7 text-zinc-400 sm:text-xl">
                Your repo&apos;s AI teammate for safe, reviewable code changes.
              </p>
            </div>

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
                  className="inline-flex min-h-12 items-center justify-center rounded-full bg-white px-5 text-sm font-semibold text-black transition hover:bg-zinc-200 disabled:cursor-not-allowed disabled:bg-zinc-500 disabled:text-zinc-900"
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

        <section className="grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(340px,0.65fr)]">
          <Panel title="Agent Flight Recorder" eyebrow="Execution timeline">
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

          <div className="grid gap-6">
            <ChangedFilesPanel run={run} />
            <Panel title="Test Results" eyebrow="Verification">
              {run && testSummary ? (
                <div className="rounded-[15px] bg-[#1c1c1c] p-4 ring-1 ring-white/10">
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
                    className="mt-4 rounded-full bg-black/30 px-3 py-2 text-xs font-medium text-zinc-300 ring-1 ring-white/10 transition hover:text-white"
                    onClick={() => setShowTestLog((current) => !current)}
                    type="button"
                  >
                    {showTestLog ? "Hide test log" : "Show test log"}
                  </button>
                  {showTestLog ? (
                    <pre className="mt-3 max-h-56 overflow-auto rounded-[10px] bg-black/45 p-3 font-mono text-xs leading-5 text-zinc-300 ring-1 ring-white/10">
                      {getTesterLog(run)}
                    </pre>
                  ) : null}
                </div>
              ) : (
                <EmptyPanel label="Test output is waiting for execution." />
              )}
            </Panel>
          </div>
        </section>

        <section className="grid gap-6 lg:grid-cols-[0.75fr_1.25fr]">
          <Panel title="Safety Panel" eyebrow="Action guardrails">
            {run ? (
              <div className="grid gap-4">
                <div className="rounded-[15px] bg-[#1c1c1c] p-4 ring-1 ring-white/10">
                  <p className="text-sm text-zinc-500">Risk score</p>
                  <div className="mt-3">
                    <StatusPill value={run.safety.risk_score} />
                  </div>
                </div>
                <div className="grid gap-3">
                  {run.safety.blocked_actions.map((action) => (
                    <article
                      className="rounded-[15px] bg-orange-400/10 p-4 ring-1 ring-orange-300/15"
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
            className="bg-[linear-gradient(135deg,rgba(212,77,240,0.22),rgba(20,20,20,1)_38%,rgba(0,153,255,0.16))]"
            title="Memory Panel"
            eyebrow="Repository learning"
          >
            {run ? (
              <div className="grid gap-4 md:grid-cols-3">
                <MemoryColumn
                  title="Before"
                  items={friendlyMemoryItems(run.memory.before)}
                />
                <MemoryColumn title="Learned" items={run.memory.learned} featured />
                <MemoryColumn title="Used" items={run.memory.used} />
              </div>
            ) : (
              <EmptyPanel label="BroPilot memory will grow from each reviewed run." />
            )}
          </Panel>
        </section>

        <PrSummaryPanel run={run} />
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
    <div className="rounded-[30px] bg-[linear-gradient(135deg,#d44df0_0%,#6a4cf5_46%,#ff7a3d_100%)] p-[1px]">
      <div className="flex h-full flex-col justify-between rounded-[30px] bg-[#101010]/90 p-6 backdrop-blur sm:p-8">
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
              <h2 className="text-3xl font-semibold leading-tight text-white">
                {run.pr_summary.title}
              </h2>
              <p className="mt-4 text-sm leading-6 text-zinc-400">{run.task}</p>
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

        <div className="mt-8 grid grid-cols-2 gap-3">
          {runMeta ? (
            runMeta.map((item) => (
              <div
                className="rounded-[15px] bg-white/10 p-4 ring-1 ring-white/10"
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
              <div className="rounded-[15px] bg-white/10 p-4 ring-1 ring-white/10">
                <p className="text-xs text-zinc-500">Workflow</p>
                <p className="mt-2 text-sm font-medium text-white">5 agents</p>
              </div>
              <div className="rounded-[15px] bg-white/10 p-4 ring-1 ring-white/10">
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

  return (
    <li className="grid gap-4 sm:grid-cols-[48px_1fr]">
      <div className="flex items-start gap-3 sm:flex-col sm:items-center">
        <div className="grid size-12 shrink-0 place-items-center rounded-full bg-white text-sm font-semibold text-black">
          {index + 1}
        </div>
        {!isLast ? (
          <div className="hidden h-full min-h-12 w-px bg-white/10 sm:block" />
        ) : null}
      </div>
      <article className="rounded-[15px] bg-[#1c1c1c] p-4 ring-1 ring-white/10">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h3 className="text-base font-semibold text-white">{agent.name}</h3>
            <p className="mt-2 text-sm leading-6 text-zinc-400">
              {agent.summary}
            </p>
          </div>
          <StatusPill value={agent.status} />
        </div>

        {highlights.length ? (
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            {highlights.map((highlight) => (
              <div
                className="rounded-[10px] bg-black/25 px-3 py-2 text-sm text-zinc-300 ring-1 ring-white/10"
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
              className="mt-4 rounded-full bg-black/30 px-3 py-2 text-xs font-medium text-zinc-300 ring-1 ring-white/10 transition hover:text-white"
              onClick={toggleLog}
              type="button"
            >
              {showLog ? "Hide technical log" : "Show technical log"}
            </button>
            {showLog ? (
              <pre className="mt-3 max-h-64 overflow-auto rounded-[10px] bg-black/45 p-3 font-mono text-xs leading-5 text-zinc-300 ring-1 ring-white/10">
                {agent.details}
              </pre>
            ) : null}
          </>
        ) : null}
      </article>
    </li>
  );
}

function ChangedFilesPanel({ run }: { run: RunResponse | null }) {
  return (
    <Panel title="Changed Files" eyebrow="Patch surface">
      {run ? (
        run.changed_files.length ? (
          <div className="grid gap-3">
            {run.changed_files.map((file) => (
              <article
                className="rounded-[15px] bg-[#1c1c1c] p-4 ring-1 ring-white/10"
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
  return (
    <Panel title="PR Summary Panel" eyebrow="Ready for review">
      {run ? (
        <div className="grid gap-5 lg:grid-cols-[0.8fr_1.2fr]">
          <div className="rounded-[15px] bg-white p-5 text-black">
            <p className="text-xs font-medium uppercase text-zinc-500">
              Review title
            </p>
            <h2 className="mt-3 text-2xl font-semibold leading-tight">
              {run.pr_summary.title}
            </h2>
            <div className="mt-5 flex flex-wrap gap-2">
              <span className="rounded-full bg-black px-3 py-1.5 text-xs font-medium text-white">
                {run.tests.command} {run.tests.status}
              </span>
              <span className="rounded-full bg-zinc-100 px-3 py-1.5 text-xs font-medium text-zinc-700">
                Human review required
              </span>
            </div>
          </div>
          <div className="grid gap-3">
            {run.pr_summary.body.map((item) => (
              <div
                className="rounded-[15px] bg-[#1c1c1c] p-4 text-sm leading-6 text-zinc-300 ring-1 ring-white/10"
                key={item}
              >
                {item}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <EmptyPanel label="The generated PR title and summary will be shown after BroPilot completes." />
      )}
    </Panel>
  );
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
      className={`rounded-[15px] p-4 ring-1 ${
        featured
          ? "bg-white text-black ring-white/20"
          : "bg-black/25 text-white ring-white/10"
      }`}
    >
      <h3
        className={`text-sm font-semibold ${
          featured ? "text-black" : "text-white"
        }`}
      >
        {title}
      </h3>
      {items.length > 0 ? (
        <ul className="mt-4 grid gap-3">
          {items.map((item) => (
            <li
              className={`text-sm leading-6 ${
                featured ? "text-zinc-700" : "text-zinc-400"
              }`}
              key={item}
            >
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p
          className={`mt-4 text-sm leading-6 ${
            featured ? "text-zinc-600" : "text-zinc-500"
          }`}
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
    return [
      "SDK runner used with CLI disabled",
      `Changed ${run.changed_files.length} file${
        run.changed_files.length === 1 ? "" : "s"
      }`,
      fileNames ? `${fileNames} updated` : "No code changes captured",
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
    return ["Known files preloaded", "Read/write tools preferred"];
  }

  return [];
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

  return {
    label: run.tests.summary || "Verification output captured.",
  };
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
