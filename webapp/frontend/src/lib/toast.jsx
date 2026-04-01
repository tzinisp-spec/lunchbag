import { createContext, useContext, useState, useCallback, useRef } from 'react'

const ToastContext = createContext(null)

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const counter = useRef(0)

  const dismiss = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const addToast = useCallback((type, message, options = {}) => {
    const id = ++counter.current
    const duration = options.duration ?? (type === 'error' ? 8000 : type === 'warning' ? 6000 : 4500)
    setToasts(prev => [...prev, { id, type, message, action: options.action ?? null }])
    setTimeout(() => dismiss(id), duration)
  }, [dismiss])

  return (
    <ToastContext.Provider value={{ addToast, dismiss, toasts }}>
      {children}
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
