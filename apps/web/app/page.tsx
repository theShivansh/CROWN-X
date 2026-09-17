import { StartActions } from "@/components/start-actions";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-[72ch] flex-col justify-center gap-8 px-4 py-12">
      <div className="flex flex-col gap-3">
        <p className="font-mono text-xs text-text-subtle">CROWN-X</p>
        <h1 className="text-2xl font-semibold tracking-[-0.02em] text-text">
          Answers from your project documents, with the passages behind them.
        </h1>
        <p className="text-base text-text-muted">
          Upload the versions of a brief, a spec or an organiser update, then ask a question. Every
          result points at the chunk of the document it came from.
        </p>
      </div>
      <StartActions demoWorkspaceId={process.env.NEXT_PUBLIC_DEMO_WORKSPACE_ID} />
    </main>
  );
}
