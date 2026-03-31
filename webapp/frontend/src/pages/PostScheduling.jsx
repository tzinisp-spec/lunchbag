export default function PostScheduling() {
  return (
    <div className="p-4 sm:p-6 md:p-8">
      <div className="mb-8">
        <p className="text-xs text-[var(--c-text-3)] uppercase tracking-wider mb-1">Workflow</p>
        <h1 className="text-2xl text-[var(--c-text-1)] font-semibold">Auto Scheduling</h1>
      </div>
      <div className="bg-[var(--c-surface)] border border-[var(--c-border)] rounded-lg p-12 flex flex-col items-center justify-center text-center">
        <div className="w-12 h-12 rounded-full bg-[var(--c-surface-2)] flex items-center justify-center mb-4">
          <span className="text-2xl">🗓</span>
        </div>
        <div className="text-[var(--c-text-1)] font-medium mb-2">Coming soon</div>
        <div className="text-[var(--c-text-3)] text-sm max-w-sm">
          Scheduled posts and publication timeline will appear here.
        </div>
      </div>
    </div>
  )
}
