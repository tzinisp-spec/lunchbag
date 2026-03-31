import { AlertTriangle, Trash2 } from 'lucide-react'

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  variant = 'danger',
  onConfirm,
  onCancel,
}) {
  if (!open) return null

  const confirmCls = variant === 'danger'
    ? 'bg-red-700 hover:bg-red-600 text-white'
    : 'bg-orange-600 hover:bg-orange-500 text-white'

  const Icon    = variant === 'danger' ? Trash2 : AlertTriangle
  const iconCls = variant === 'danger' ? 'text-red-400' : 'text-orange-400'
  const iconBg  = variant === 'danger' ? 'bg-red-500/10' : 'bg-orange-500/10'

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/70" onClick={onCancel} />
      <div className="relative bg-[var(--c-surface)] border border-[var(--c-border-2)] rounded-xl p-6 w-full max-w-sm mx-4 shadow-2xl">
        <div className={`w-11 h-11 rounded-full ${iconBg} flex items-center justify-center mb-4`}>
          <Icon size={20} className={iconCls} />
        </div>
        <h3 className="text-[var(--c-text-1)] font-semibold text-base mb-2">{title}</h3>
        <p className="text-[var(--c-text-2)] text-sm leading-relaxed mb-6">{message}</p>
        <div className="flex gap-3">
          <button
            onClick={onCancel}
            className="flex-1 bg-[var(--c-surface-2)] hover:bg-[var(--c-surface-3)] text-[var(--c-text-1b)] text-sm font-medium py-2 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={`flex-1 text-sm font-medium py-2 rounded-lg transition-colors ${confirmCls}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
