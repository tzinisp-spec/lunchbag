export default function ContentPlanning() {
  return (
    <div className="p-8">
      <div className="mb-8">
        <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Workflow</p>
        <h1 className="text-2xl text-white font-semibold">Content Planning</h1>
      </div>
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-12 flex flex-col items-center justify-center text-center">
        <div className="w-12 h-12 rounded-full bg-gray-800 flex items-center justify-center mb-4">
          <span className="text-2xl">📅</span>
        </div>
        <div className="text-white font-medium mb-2">Coming soon</div>
        <div className="text-gray-500 text-sm max-w-sm">
          Weekly posting calendars and content briefs will appear here once the Content Planner agent runs.
        </div>
      </div>
    </div>
  )
}
