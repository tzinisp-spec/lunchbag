import { useToast } from '../lib/toast'
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react'

const CONFIGS = {
  success: { Icon: CheckCircle,  bar: 'bg-green-500',  iconCls: 'text-green-400'  },
  error:   { Icon: XCircle,      bar: 'bg-red-500',    iconCls: 'text-red-400'    },
  warning: { Icon: AlertTriangle,bar: 'bg-orange-500', iconCls: 'text-orange-400' },
  info:    { Icon: Info,         bar: 'bg-blue-500',   iconCls: 'text-blue-400'   },
}

export default function ToastContainer() {
  const { toasts, dismiss } = useToast()
  if (!toasts.length) return null
  return (
    <div className="fixed bottom-5 right-5 z-[200] flex flex-col gap-2 items-end pointer-events-none">
      {toasts.map(t => <Toast key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />)}
    </div>
  )
}

function Toast({ toast, onDismiss }) {
  const cfg  = CONFIGS[toast.type] ?? CONFIGS.info
  const Icon = cfg.Icon
  return (
    <div className="pointer-events-auto flex items-start gap-3 bg-[var(--c-surface)] border border-[var(--c-border-2)] rounded-xl shadow-xl px-4 py-3 min-w-[280px] max-w-[360px] relative overflow-hidden toast-enter">
      <div className={`absolute left-0 top-0 bottom-0 w-1 rounded-l-xl ${cfg.bar}`} />
      <Icon size={16} className={`shrink-0 mt-0.5 ${cfg.iconCls}`} />
      <div className="flex-1 min-w-0">
        <p className="text-sm text-[var(--c-text-1)] leading-snug">{toast.message}</p>
        {toast.action && (
          <button
            onClick={() => { toast.action.onClick(); onDismiss() }}
            className="mt-1 text-xs text-blue-400 hover:text-blue-300 transition-colors"
          >
            {toast.action.label} →
          </button>
        )}
      </div>
      <button onClick={onDismiss} className="shrink-0 text-[var(--c-text-4)] hover:text-[var(--c-text-2)] transition-colors mt-0.5">
        <X size={13} />
      </button>
    </div>
  )
}
