import Link from "next/link";

const workflowCards = [
  {
    title: "Code Pilot",
    description:
      "Turn an engineering task into a review-ready code change with scoped context, constrained agent execution, independent tests, diffs, safety checks, and a PR summary.",
    href: "/code-pilot",
  },
  {
    title: "Memo Pilot",
    description:
      "Turn company notes into a structured memo draft with growth signals, risk flags, diligence questions, and missing-evidence checks.",
    href: "/memo-pilot",
  },
  {
    title: "Ops Pilot",
    description:
      "Turn messy operating notes into bottlenecks, automation opportunities, priority rankings, and a 30-day action plan.",
    href: "/ops-pilot",
  },
];

const flowSteps = [
  "Context Intake",
  "Scoped Plan",
  "Constrained Agent",
  "Independent Verification",
  "Flight Recorder",
  "Human Review",
];

const trustCards = [
  {
    title: "Human-in-the-loop by default",
    marker: "H",
  },
  {
    title: "Independent verification",
    marker: "V",
  },
  {
    title: "Flight Recorder audit trail",
    marker: "F",
  },
  {
    title: "Swappable model and runner layer",
    marker: "S",
  },
];

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

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-white text-zinc-950">
      <TopNav />

      <section className="mx-auto grid w-full max-w-7xl gap-12 px-5 pb-16 pt-20 sm:px-8 sm:pt-24 lg:px-10 lg:pb-24">
        <div className="mx-auto max-w-6xl text-center">
          <h1 className="font-copperplate text-5xl font-semibold leading-[1.02] text-zinc-950 sm:text-6xl lg:text-7xl">
            Review-ready AI workflows for high-trust automation
          </h1>
          <p className="mx-auto mt-6 max-w-3xl text-lg leading-8 text-zinc-600 sm:text-xl">
            BroPilot Workbench turns ambiguous work into structured, verified,
            human-reviewable outputs, starting with safe agentic code changes,
            then applying the same workflow pattern to memo drafting and
            portfolio operations.
          </p>
          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              className="inline-flex min-h-11 w-full items-center justify-center rounded-md bg-zinc-950 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-zinc-800 sm:w-auto"
              href="/code-pilot"
            >
              Open Code Pilot
            </Link>
            <Link
              className="inline-flex min-h-11 w-full items-center justify-center rounded-md border border-zinc-200 bg-white px-5 text-sm font-semibold text-zinc-950 shadow-sm transition hover:bg-zinc-50 sm:w-auto"
              href="/architecture"
            >
              View Workflow Pattern
            </Link>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          {workflowCards.map((card) => (
            <Link
              className="group flex min-h-[360px] flex-col justify-between rounded-lg border border-zinc-300 bg-zinc-100 p-7 text-center shadow-[0_1px_1px_rgba(0,0,0,0.04),0_10px_30px_rgba(0,0,0,0.05)] transition hover:-translate-y-0.5 hover:border-zinc-400 hover:bg-zinc-50 hover:shadow-[0_1px_1px_rgba(0,0,0,0.05),0_18px_44px_rgba(0,0,0,0.08)]"
              href={card.href}
              key={card.title}
            >
              <div className="flex flex-1 flex-col items-center justify-center">
                <div className="mb-7 grid size-12 place-items-center rounded-lg border border-zinc-300 bg-zinc-50 shadow-sm">
                  <span className="size-2 rounded-full bg-zinc-950" />
                </div>
                <h2 className="font-copperplate text-3xl font-semibold text-zinc-950">
                  {card.title}
                </h2>
                <div className="mt-6 max-w-sm rounded-md border border-zinc-300 bg-white/80 p-4 shadow-sm">
                  <p className="text-sm leading-6 text-zinc-600">
                    {card.description}
                  </p>
                </div>
              </div>
              <span className="mt-8 inline-flex min-h-11 w-full items-center justify-center rounded-md border border-zinc-950 bg-zinc-950 px-4 text-sm font-semibold text-white shadow-sm transition group-hover:bg-zinc-800">
                Open {card.title}
              </span>
            </Link>
          ))}
        </div>
      </section>

      <section className="border-y border-zinc-200 bg-zinc-50">
        <div className="mx-auto grid w-full max-w-7xl gap-8 px-5 py-16 sm:px-8 lg:px-10">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
            <div>
              <p className="text-sm font-medium text-zinc-500">Shared pattern</p>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight text-zinc-950 sm:text-4xl">
                One workflow pattern, multiple use cases
              </h2>
            </div>
            <Link className="text-sm font-semibold text-zinc-950 hover:text-zinc-600" href="/architecture">
              Explore the workflow pattern -&gt;
            </Link>
          </div>

          <div className="grid gap-3 lg:grid-cols-6">
            {flowSteps.map((step, index) => (
              <div
                className="relative rounded-lg border border-zinc-200 bg-white p-4 shadow-sm"
                key={step}
              >
                <span className="inline-flex min-h-7 min-w-8 items-center justify-center rounded-md bg-zinc-950 px-2 text-xs font-semibold text-white">
                  0{index + 1}
                </span>
                <p className="mt-4 whitespace-nowrap text-sm font-semibold text-zinc-950">
                  {step}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto w-full max-w-7xl px-5 py-16 sm:px-8 lg:px-10">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {trustCards.map((card) => (
            <article
              className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm"
              key={card.title}
            >
              <div className="mb-4 grid size-8 place-items-center rounded-md border border-zinc-200 bg-zinc-50 text-xs font-semibold text-zinc-950">
                {card.marker}
              </div>
              <h3 className="text-base font-semibold tracking-tight text-zinc-950">
                {card.title}
              </h3>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
