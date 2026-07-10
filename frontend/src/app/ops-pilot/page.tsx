import Link from "next/link";

const recorderSteps = [
  "Context Intake",
  "Issue Classifier",
  "Automation Recommender",
  "Human Review",
];

export default function OpsPilotPage() {
  return (
    <main className="min-h-screen bg-white text-zinc-950">
      <PlaceholderNav />
      <section className="mx-auto w-full max-w-7xl px-5 py-16 sm:px-8 lg:px-10">
        <div className="max-w-3xl">
          <p className="mb-4 inline-flex min-h-8 items-center rounded-full border border-zinc-200 bg-zinc-50 px-3 text-sm font-medium text-zinc-600">
            Architecture demo placeholder
          </p>
          <h1 className="text-5xl font-semibold tracking-tight text-zinc-950">
            Ops Pilot
          </h1>
          <p className="mt-4 text-xl leading-8 text-zinc-600">
            Messy operating notes to prioritized action plans.
          </p>
        </div>

        <div className="mt-12 grid gap-4 lg:grid-cols-[0.9fr_1fr_1.1fr]">
          <DemoPanel title="Input">
            <p className="text-sm leading-6 text-[#d0d6e0]">
              Support notes mention onboarding delays.
              <br />
              Sales calls stall on security reviews.
              <br />
              Customer success sees week-two usage dropoff.
            </p>
          </DemoPanel>
          <DemoPanel title="Flight Recorder">
            <ol className="grid gap-3">
              {recorderSteps.map((step, index) => (
                <li className="flex items-center gap-3 text-sm text-[#d0d6e0]" key={step}>
                  <span className="grid size-7 place-items-center rounded-md border border-[#34343a] bg-[#141516] text-xs font-medium text-[#828fff]">
                    {index + 1}
                  </span>
                  {step}
                </li>
              ))}
            </ol>
          </DemoPanel>
          <DemoPanel title="Output">
            <ul className="grid gap-3 text-sm leading-6 text-[#d0d6e0]">
              <li>Recurring bottlenecks and root-cause hypotheses</li>
              <li>Automation opportunities with priority rationale</li>
              <li>Implementation risks and owner handoff notes</li>
              <li>30-day action plan for human review</li>
            </ul>
          </DemoPanel>
        </div>

        <p className="mt-8 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm font-medium text-amber-900">
          Architecture demo placeholder - full workflow coming next.
        </p>
      </section>
    </main>
  );
}

function PlaceholderNav() {
  return (
    <header className="border-b border-zinc-200 bg-white">
      <nav className="mx-auto flex min-h-16 w-full max-w-7xl items-center justify-between px-5 sm:px-8 lg:px-10">
        <Link className="text-sm font-semibold text-zinc-950" href="/">
          BroPilot Workbench
        </Link>
        <Link className="text-sm font-medium text-zinc-600 hover:text-zinc-950" href="/">
          Back home
        </Link>
      </nav>
    </header>
  );
}

function DemoPanel({
  title,
  children,
}: Readonly<{
  title: string;
  children: React.ReactNode;
}>) {
  return (
    <section className="rounded-lg border border-[#23252a] bg-[#010102] p-6 shadow-[0_1px_1px_rgba(0,0,0,0.05),0_18px_48px_rgba(0,0,0,0.16)]">
      <h2 className="text-sm font-semibold uppercase tracking-[0.08em] text-[#8a8f98]">
        {title}
      </h2>
      <div className="mt-5 text-[#d0d6e0]">{children}</div>
    </section>
  );
}
