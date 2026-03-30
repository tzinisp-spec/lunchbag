export default function StatCard({ label, value, sub }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 hover:bg-gray-800/50 transition-colors">
      <div className="text-2xl text-white font-semibold mb-1">{value ?? '—'}</div>
      <div className="text-gray-400 text-sm">{label}</div>
      {sub && <div className="text-gray-600 text-xs mt-1">{sub}</div>}
    </div>
  )
}
