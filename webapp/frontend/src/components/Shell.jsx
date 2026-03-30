import Sidebar from './Sidebar'

export default function Shell({ children }) {
  return (
    <div className="flex h-screen bg-black text-white overflow-hidden">

      {/* ── Icon Rail ── */}
      <div className="w-16 bg-black border-r border-gray-900 flex flex-col items-center py-4 gap-3 shrink-0">
        <div className="w-10 h-10 bg-gray-900 rounded-lg flex items-center justify-center select-none">
          <span className="text-white font-bold text-xs leading-none">LB</span>
        </div>
        <div className="w-10 h-10 bg-orange-500 rounded-full flex items-center justify-center select-none">
          <span className="text-white font-bold text-sm">P</span>
        </div>
        <div className="flex-1" />
        <div className="w-10 h-10 border-2 border-dashed border-gray-800 rounded-lg flex items-center justify-center cursor-pointer hover:border-gray-600 transition-colors">
          <span className="text-gray-600 text-xl leading-none">+</span>
        </div>
      </div>

      {/* ── Sidebar ── */}
      <Sidebar />

      {/* ── Main content ── */}
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>

    </div>
  )
}
