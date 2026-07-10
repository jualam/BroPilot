import Link from "next/link";

const steps = [
  {
    title: "Context Intake",
    description: "Collect the repo, company notes, or operating context needed for the workflow.",
  },
  {
    title: "Scoped Plan",
    description: "Turn ambiguous work into a bounded plan with reviewable constraints.",
  },
  {
    title: "Constrained Agent",
    description: "Execute through a controlled runner while keeping the task surface narrow.",
  },
  {
    title: "Independent Verification",
    description: "Check outputs with tests, risk flags, missing evidence, or assumption review.",
  },
  {
    title: "Flight Recorder",
    description: "Record the stages, evidence, warnings, and artifacts for the human reviewer.",
  },
  {
    title: "Human Review",
    description: "Hand off a structured artifact instead of silently taking final action.",
  },
];

const workflowMappings = [
  {
    title: "Code Pilot",
    stages: [
      "Repo context",
      "Analyzer",
      "Planner",
      "Coder",
      "Tester",
      "Reviewer",
      "PR summary",
    ],
  },
  {
    title: "Memo Pilot",
    stages: [
      "Company notes",
      "Memo planner",
      "Memo draft",
      "Growth signals",
      "Risk checker",
      "Missing-evidence check",
      "Reviewer-ready memo",
    ],
  },
  {
    title: "Ops Pilot",
    stages: [
      "Operating notes",
      "Issue classifier",
      "Bottleneck analysis",
      "Automation opportunities",
      "Priority ranking",
      "Implementation plan",
      "30-day plan",
    ],
  },
];

export default function ArchitecturePage() {
  return (
    <main className="min-h-screen bg-white text-zinc-950">
      <header className="border-b border-zinc-200 bg-white">
        <nav className="mx-auto flex min-h-16 w-full max-w-7xl items-center justify-between px-5 sm:px-8 lg:px-10">
          <Link className="text-sm font-semibold text-zinc-950" href="/">
            BroPilot Workbench
          </Link>
          <Link className="text-sm font-medium text-zinc-600 hover:text-zinc-950" href="/code-pilot">
            Open Code Pilot
          </Link>
        </nav>
      </header>

      <section className="mx-auto w-full max-w-7xl px-5 py-16 sm:px-8 lg:px-10">
        <div className="mx-auto max-w-6xl text-center">
          <p className="text-sm font-medium text-zinc-500">Shared workflow pattern</p>
          <h1 className="mt-3 text-5xl font-semibold leading-tight tracking-tight text-zinc-950 sm:text-6xl">
            One workflow pattern for code, memos, and portfolio operations.
          </h1>
          <p className="mx-auto mt-5 max-w-5xl text-lg leading-8 text-zinc-600">
            BroPilot Workbench is built around controlled agent execution,
            independent verification, evidence capture, and human review. Code
            Pilot is the deepest implementation; Memo Pilot and Ops Pilot show
            how the same pattern applies to Summit-relevant workflows.
          </p>
        </div>

        <div className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {steps.map((step, index) => (
            <article
              className="group relative rounded-lg border border-zinc-200 bg-white p-6 shadow-[0_1px_1px_rgba(0,0,0,0.03),0_10px_30px_rgba(0,0,0,0.04)]"
              key={step.title}
            >
              {index < steps.length - 1 ? (
                <div className="absolute -right-3 top-9 z-10 hidden size-6 place-items-center rounded-full border border-zinc-200 bg-white text-xs font-semibold text-zinc-400 shadow-sm lg:grid">
                  -&gt;
                </div>
              ) : null}
              <span className="inline-flex min-h-7 min-w-8 items-center justify-center rounded-md bg-zinc-950 px-2 text-xs font-semibold text-white">
                0{index + 1}
              </span>
              <h2 className="mt-4 text-xl font-semibold tracking-tight text-zinc-950">
                {step.title}
              </h2>
              <p className="mt-3 text-sm leading-6 text-zinc-600">
                {step.description}
              </p>
            </article>
          ))}
        </div>

        <section className="mt-20">
          <div className="max-w-3xl">
            <p className="text-sm font-medium text-zinc-500">Workflow mapping</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight text-zinc-950 sm:text-4xl">
              How the pattern maps across workflows
            </h2>
          </div>

          <div className="mt-8 grid gap-5 lg:grid-cols-3">
            {workflowMappings.map((mapping) => (
              <article
                className="flex min-h-[560px] flex-col rounded-lg border border-zinc-200 bg-white p-6 shadow-[0_1px_1px_rgba(0,0,0,0.03),0_12px_36px_rgba(0,0,0,0.05)]"
                key={mapping.title}
              >
                <h3 className="text-center text-2xl font-semibold tracking-tight text-zinc-950">
                  {mapping.title}
                </h3>

                <ol className="mt-7 flex flex-1 flex-col">
                  {mapping.stages.map((stage, index) => (
                    <li className="flex flex-1 flex-col" key={stage}>
                      <div className="flex min-h-12 items-center justify-center rounded-md border border-zinc-200 bg-zinc-50 px-4 text-center text-sm font-medium text-zinc-800 shadow-sm">
                        {stage}
                      </div>
                      {index < mapping.stages.length - 1 ? (
                        <div className="grid flex-1 min-h-5 place-items-center">
                          <span className="relative block h-5 w-px bg-zinc-200">
                            <span className="absolute -bottom-0.5 left-1/2 size-2 -translate-x-1/2 rotate-45 border-b border-r border-zinc-400" />
                          </span>
                        </div>
                      ) : null}
                    </li>
                  ))}
                </ol>
              </article>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}
