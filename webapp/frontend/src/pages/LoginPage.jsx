import { useState } from 'react'
import { useAuth } from '../lib/auth'

export default function LoginPage() {
  const { login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username.trim(), password)
    } catch (e) {
      const msg = e?.message ?? ''
      setError(msg.includes('401')
        ? 'Invalid username or password.'
        : 'Cannot connect to server. Make sure it is running.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[var(--c-page)] flex items-center justify-center px-4">
      <div className="w-full max-w-sm">

        {/* Logo */}
        <div className="flex items-center gap-3 mb-8 justify-center">
          <div className="w-10 h-10 bg-[var(--c-icon-box)] rounded-xl flex items-center justify-center">
            <span className="text-[var(--c-text-1)] font-bold text-sm">C</span>
          </div>
          <span className="text-[var(--c-text-1)] font-semibold text-lg tracking-tight">COMAP</span>
        </div>

        {/* Card */}
        <div className="bg-[var(--c-sidebar)] border border-[var(--c-border)] rounded-xl p-8 shadow-lg">
          <h1 className="text-[var(--c-text-1)] font-semibold text-lg mb-1">Sign in</h1>
          <p className="text-[var(--c-text-3)] text-sm mb-6">Enter your credentials to continue.</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs text-[var(--c-text-2)] mb-1.5 font-medium">Username</label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                autoComplete="username"
                autoFocus
                required
                className="w-full bg-[var(--c-surface-2)] border border-[var(--c-border)] rounded-lg px-3 py-2.5 text-sm text-[var(--c-text-1)] placeholder:text-[var(--c-text-3)] outline-none focus:border-[var(--c-border-2)] transition-colors"
              />
            </div>

            <div>
              <label className="block text-xs text-[var(--c-text-2)] mb-1.5 font-medium">Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                autoComplete="current-password"
                required
                className="w-full bg-[var(--c-surface-2)] border border-[var(--c-border)] rounded-lg px-3 py-2.5 text-sm text-[var(--c-text-1)] placeholder:text-[var(--c-text-3)] outline-none focus:border-[var(--c-border-2)] transition-colors"
              />
            </div>

            {error && (
              <p className="text-red-400 text-sm">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-[var(--c-text-1)] text-[var(--c-page)] font-medium text-sm py-2.5 rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 mt-2"
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>

      </div>
    </div>
  )
}
