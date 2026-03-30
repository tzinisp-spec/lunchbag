const STYLES = {
  complete:     'text-green-500',
  in_progress:  'text-blue-500',
  empty:        'text-gray-500',
  approved:     'text-green-500',
  needs_review: 'text-orange-400',
  regen:        'text-red-400',
  pending:      'text-gray-400',
}

const LABELS = {
  complete:     'Complete',
  in_progress:  'In Progress',
  empty:        'Empty',
  approved:     'Approved',
  needs_review: 'Needs Review',
  regen:        'Regen',
  pending:      'Pending',
}

const DOTS = {
  complete:    'bg-green-500',
  in_progress: 'bg-blue-500',
  empty:       'bg-gray-500',
}

export default function StatusBadge({ status, dot = false }) {
  const cls = STYLES[status] ?? 'text-gray-400'
  const label = LABELS[status] ?? status
  return (
    <span className={`flex items-center gap-1.5 text-sm font-medium ${cls}`}>
      {dot && <span className={`w-2 h-2 rounded-full ${DOTS[status] ?? 'bg-gray-500'}`} />}
      {label}
    </span>
  )
}
