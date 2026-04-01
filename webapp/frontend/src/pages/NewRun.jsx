import { useEffect, useRef, useState, useCallback } from 'react'
import {
  Play, Square, Pause, RotateCcw, Upload, X,
  ChevronDown, ChevronUp, ImageIcon, Package, FileText, Settings, Check,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'

const SET_LABELS = { '1': 'Set 1', '2': 'Set 2', '3': 'Set 3' }

function fmtElapsed(sec) {
  if (!sec) return '0s'
  if (sec < 60) return `${sec}s`
  const m = Math.floor(sec / 60)
  if (m < 60) return `${m}'`
  const h = Math.floor(m / 60), r = m % 60
  return r ? `${h}h ${r}'` : `${h}h`
}

const CONFIG_DEFAULTS = {
  product_focus:     'Original thermal lunch bag — cotton exterior, waterproof interior, Thermo Hot&Cold mechanism, H21cm x W16cm x D24cm, various prints and colours',
  product_materials: 'Cotton exterior, waterproof interior lining, thermal insulation, fabric straps. Surface has a soft textile feel — not leather, not plastic, not glossy. Bold graphic prints on cotton.',
  target_audience:   'Women and men 25–45, Greece and Europe, active lifestyle, health-conscious, daily commuters, parents, office workers, anyone who carries food on the go',
}

const STATE_LABEL = { idle: 'Idle', running: 'Running', paused: 'Paused', stopping: 'Stopping' }
const STATE_CLS   = {
  idle:     'bg-[var(--c-surface-2)] text-[var(--c-text-3)]',
  running:  'bg-green-500/15 text-green-400 border border-green-500/30',
  paused:   'bg-yellow-500/15 text-yellow-400 border border-yellow-500/30',
  stopping: 'bg-red-500/15 text-red-400 border border-red-500/30',
}

// ── useSaved — flash "Saved" for 1.5s after an autosave ──────────────────────
function useSaved() {
  const [saved, setSaved] = useState(false)
  const timerRef = useRef(null)
  const flash = useCallback(() => {
    setSaved(true)
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => setSaved(false), 1500)
  }, [])
  useEffect(() => () => clearTimeout(timerRef.current), [])
  return [saved, flash]
}

export default function NewRun() {
  const { addToast } = useToast()

  // Run state
  const [runStatus,    setRunStatus]    = useState(null)
  const [elapsed,      setElapsed]      = useState(0)
  const elapsedBase = useRef(null)

  // Assets
  const [assets,       setAssets]       = useState({ references: {}, products: [] })
  const [assetsOpen,   setAssetsOpen]   = useState(true)

  // Concept — mirrors concept.md
  const [concept,      setConcept]      = useState('')
  const [conceptOpen,  setConceptOpen]  = useState(true)
  const [conceptSaved, flashConceptSaved] = useSaved()

  // Persistent config — mirrors lunchbag/config/shoot_config.json
  const [shootConfig,  setShootConfig]  = useState(CONFIG_DEFAULTS)
  const [configSaved,  flashConfigSaved] = useSaved()
  const [advancedOpen, setAdvancedOpen] = useState(false)

  // Shoot name — ephemeral, not persisted (just for this run)
  const [shootName,    setShootName]    = useState('')
  const [nameSuggestion, setNameSuggestion] = useState('')
  const [nameError,    setNameError]    = useState('')

  // Log terminal
  const [lines,        setLines]        = useState([])
  const logRef    = useRef(null)
  const esRef     = useRef(null)

  const state    = runStatus?.state ?? 'idle'
  const isActive = state === 'running' || state === 'paused'

  // Collapse and lock all sections when a run starts
  useEffect(() => {
    if (isActive) {
      setAssetsOpen(false)
      setConceptOpen(false)
      setAdvancedOpen(false)
    }
  }, [isActive])

  // ── Poll run status ────────────────────────────────────────────────────────
  const fetchStatus = useCallback(() => {
    api.runStatus()
      .then(s => {
        setRunStatus(s)
        if (s.state !== 'idle' && s.started_at) {
          elapsedBase.current = { started_at: s.started_at }
        }
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    fetchStatus()
    const id = setInterval(fetchStatus, 4000)
    return () => clearInterval(id)
  }, [fetchStatus])

  // ── Elapsed counter ────────────────────────────────────────────────────────
  useEffect(() => {
    if (state === 'idle') { setElapsed(0); return }
    if (state === 'paused') return
    const id = setInterval(() => {
      if (!elapsedBase.current) return
      const base = new Date(elapsedBase.current.started_at + 'Z').getTime()
      setElapsed(Math.floor((Date.now() - base) / 1000))
    }, 1000)
    return () => clearInterval(id)
  }, [state])

  // ── SSE log stream ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!isActive) return
    const es = new EventSource(api.runLogsUrl())
    esRef.current = es
    es.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.done) { es.close(); return }
      if (data.line != null) setLines(prev => [...prev.slice(-999), data.line])
    }
    es.onerror = () => es.close()
    return () => { es.close(); esRef.current = null }
  }, [isActive])

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [lines])

  // ── Load everything on mount ───────────────────────────────────────────────
  const loadAssets = useCallback(() => {
    api.runAssets().then(setAssets).catch(() => {})
  }, [])

  useEffect(() => {
    loadAssets()
    api.concept().then(d => setConcept(d.text || '')).catch(() => {})
    api.runConfigGet()
      .then(data => setShootConfig({ ...CONFIG_DEFAULTS, ...data }))
      .catch(()  => setShootConfig({ ...CONFIG_DEFAULTS }))
  }, [loadAssets])

  // ── Fetch name suggestion ──────────────────────────────────────────────────
  useEffect(() => {
    api.runValidateName('_probe', '')
      .then(d => {
        setNameSuggestion(d.suggestion)
        setShootName(n => n || d.suggestion)
      })
      .catch(() => {})
  }, [])

  // ── Auto-save helpers ──────────────────────────────────────────────────────
  const saveConfig = useCallback(async (patch) => {
    try {
      await api.runConfigSave(patch)
      flashConfigSaved()
    } catch {}
  }, [flashConfigSaved])

  const saveConcept = useCallback(async (text) => {
    try {
      await api.conceptSave(text)
      flashConceptSaved()
    } catch {}
  }, [flashConceptSaved])

  const handleConfigBlur = (key, value) => {
    setShootConfig(c => ({ ...c, [key]: value }))
    saveConfig({ [key]: value })
  }

  // ── Name validation ────────────────────────────────────────────────────────
  const checkName = useCallback(async (name) => {
    if (!name) { setNameError(''); return }
    try {
      const res = await api.runValidateName(name, '')
      setNameError(res.exists ? `"${name}" already exists — choose a different name` : '')
    } catch { setNameError('') }
  }, [])

  // ── Controls ───────────────────────────────────────────────────────────────
  const handleStart = async () => {
    // Save concept first (in case of unsaved edits)
    try { await api.conceptSave(concept) } catch {}

    const runConfig = {
      shoot_name: shootName || nameSuggestion,
      ...(shootConfig ?? {}),
    }
    try {
      await api.runStart(runConfig)
      setLines([])
      fetchStatus()
      addToast('info', `Starting ${runConfig.shoot_name || 'new shoot'}`)
    } catch (e) {
      addToast('error', e.message || 'Failed to start run')
    }
  }

  const handleStop = async () => {
    try {
      await api.runStop()
      fetchStatus()
      addToast('warning', 'Run stopped')
    } catch (e) {
      addToast('error', e.message || 'Failed to stop')
    }
  }

  const handlePause = async () => {
    try {
      await (state === 'paused' ? api.runResume() : api.runPause())
      fetchStatus()
    } catch (e) {
      addToast('error', e.message || 'Failed')
    }
  }

  // ── Asset actions ──────────────────────────────────────────────────────────
  const handleUpload = async (target, files) => {
    if (!files.length) return
    try {
      await api.runUpload(target, Array.from(files))
      loadAssets()
      addToast('success', `${files.length} file${files.length === 1 ? '' : 's'} uploaded`)
    } catch {
      addToast('error', 'Upload failed')
    }
  }

  const handleDeleteAsset = async (target, filename) => {
    try {
      await api.runDeleteAsset(target, filename)
      loadAssets()
    } catch {
      addToast('error', 'Delete failed')
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="p-4 sm:p-6 md:p-8 max-w-5xl">

      {/* Header */}
      <div className="mb-8 flex items-start justify-between">
        <div>
          <p className="text-xs text-[var(--c-text-3)] uppercase tracking-wider mb-1">Workflow</p>
          <h1 className="text-xl text-[var(--c-text-1)] font-semibold">New Shoot</h1>
        </div>
        <div className={`text-xs font-medium px-2.5 py-1 rounded-full ${STATE_CLS[state] ?? STATE_CLS.idle}`}>
          {STATE_LABEL[state] ?? state}
          {state !== 'idle' && elapsed > 0 && (
            <span className="ml-1.5 opacity-70">{fmtElapsed(elapsed)}</span>
          )}
        </div>
      </div>

      {/* ── Active run panel ── */}
      {isActive && (
        <div className="mb-8 bg-[var(--c-surface)] border border-[var(--c-border)] rounded-xl overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--c-border)] bg-[var(--c-surface-2)]">
            <button
              onClick={handlePause}
              className="flex items-center gap-2 text-sm px-3 py-1.5 rounded-lg border border-[var(--c-border-2)] text-[var(--c-text-1b)] hover:bg-[var(--c-surface-3)] transition-colors"
            >
              {state === 'paused' ? <><RotateCcw size={13} /> Resume</> : <><Pause size={13} /> Pause</>}
            </button>
            <button
              onClick={handleStop}
              className="flex items-center gap-2 text-sm px-3 py-1.5 rounded-lg border border-red-500/30 text-red-400 hover:bg-red-500/10 transition-colors"
            >
              <Square size={13} /> Stop
            </button>
            {state === 'paused' && (
              <span className="ml-2 text-xs text-yellow-400 animate-pulse">⏸ Pipeline frozen</span>
            )}
          </div>
          <div
            ref={logRef}
            className="h-80 overflow-y-auto font-mono text-[11px] leading-relaxed text-[var(--c-text-2)] p-4 bg-[var(--c-page)]"
          >
            {lines.length === 0
              ? <span className="text-[var(--c-text-4)]">Waiting for output…</span>
              : lines.map((l, i) => <LogLine key={i} line={l} />)
            }
          </div>
        </div>
      )}

      {/* ── Log replay when stopped ── */}
      {!isActive && lines.length > 0 && (
        <div className="mb-8 bg-[var(--c-surface)] border border-[var(--c-border)] rounded-xl overflow-hidden">
          <div className="px-4 py-2.5 border-b border-[var(--c-border)] text-xs text-[var(--c-text-3)] uppercase tracking-wider">
            Last run output
          </div>
          <div
            ref={logRef}
            className="h-48 overflow-y-auto font-mono text-[11px] leading-relaxed text-[var(--c-text-2)] p-4 bg-[var(--c-page)]"
          >
            {lines.map((l, i) => <LogLine key={i} line={l} />)}
          </div>
        </div>
      )}

      {/* ── Shoot Identity ── */}
      <div className={`bg-[var(--c-surface)] border border-[var(--c-border)] rounded-xl p-5 mb-4 ${isActive ? 'opacity-60' : ''}`}>
        <p className="text-xs text-[var(--c-text-3)] uppercase tracking-wider mb-4">Shoot Identity</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label="Shoot Name">
            <input
              type="text"
              placeholder={nameSuggestion || 'e.g. Shoot12'}
              value={shootName}
              onChange={e => { setShootName(e.target.value); setNameError('') }}
              onBlur={() => checkName(shootName)}
              disabled={isActive}
              className={`${inputCls} ${nameError ? 'border-red-500/60' : ''}`}
            />
            {nameError
              ? <p className="mt-1 text-xs text-red-400">{nameError}</p>
              : <p className="mt-1 text-xs text-[var(--c-text-4)]">Leave blank to use {nameSuggestion || 'auto-generated name'}</p>
            }
          </Field>
          <Field label="Total Images">
            <input
              type="number"
              min={3} max={300} step={1}
              value={shootConfig.images_per_sprint ?? '50'}
              onChange={e => setShootConfig(c => ({ ...c, images_per_sprint: e.target.value }))}
              onBlur={e => handleConfigBlur('images_per_sprint', e.target.value)}
              disabled={isActive}
              className={inputCls}
            />
            <p className="mt-1 text-xs text-[var(--c-text-4)]">
              {(() => {
                const n = parseInt(shootConfig.images_per_sprint) || 50
                const base = Math.floor(n / 3), rem = n % 3
                const s = i => base + (i <= rem ? 1 : 0)
                return `3 sets · ${s(1)} / ${s(2)} / ${s(3)} images`
              })()}
            </p>
          </Field>
        </div>
        <SavedBadge visible={configSaved} />
      </div>

      {/* ── Reference Images ── */}
      <Section
        title="Reference Images"
        icon={<ImageIcon size={14} />}
        open={assetsOpen}
        onToggle={() => setAssetsOpen(o => !o)}
        disabled={isActive}
        className="mb-4"
      >
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {['1', '2', '3'].map(s => (
            <AssetSet
              key={s}
              label={SET_LABELS[s]}
              target={`references_${s}`}
              files={assets.references?.[s] ?? []}
              onUpload={files => handleUpload(`references_${s}`, files)}
              onDelete={filename => handleDeleteAsset(`references_${s}`, filename)}
              disabled={isActive}
            />
          ))}
        </div>
      </Section>

      {/* ── Product Images ── */}
      <Section
        title="Product Images"
        icon={<Package size={14} />}
        open={assetsOpen}
        onToggle={() => setAssetsOpen(o => !o)}
        disabled={isActive}
        className="mb-4"
      >
        <AssetSet
          target="products"
          files={assets.products ?? []}
          onUpload={files => handleUpload('products', files)}
          onDelete={filename => handleDeleteAsset('products', filename)}
          disabled={isActive}
          flat
        />
      </Section>

      {/* ── Campaign Concept ── */}
      <Section
        title="Campaign Concept"
        icon={<FileText size={14} />}
        open={conceptOpen}
        onToggle={() => setConceptOpen(o => !o)}
        disabled={isActive}
        className="mb-4"
        badge={<SavedBadge visible={conceptSaved} inline />}
      >
        <p className="text-xs text-[var(--c-text-4)] mb-3">
          Mirrors <span className="font-mono">concept.md</span> — describes the shoot campaign, per-set locations, props, and mood. Read by AI agents at run start.
        </p>
        <textarea
          rows={14}
          value={concept}
          onChange={e => setConcept(e.target.value)}
          onBlur={e => saveConcept(e.target.value)}
          disabled={isActive}
          placeholder="CAMPAIGN CONCEPT: ..."
          className={`${inputCls} resize-y font-mono text-xs leading-relaxed`}
        />
      </Section>

      {/* ── Advanced Customization ── */}
      <Section
        title="Advanced Customization"
        icon={<Settings size={14} />}
        open={advancedOpen}
        onToggle={() => setAdvancedOpen(o => !o)}
        disabled={isActive}
        className="mb-6"
        badge={<SavedBadge visible={configSaved} inline />}
      >
        <p className="text-xs text-[var(--c-text-4)] mb-4">
          Mirrors <span className="font-mono">lunchbag/config/shoot_config.json</span> — these rarely change between shoots.
        </p>
        <Field label="Product Focus" className="mb-4">
          <textarea rows={3}
            value={shootConfig.product_focus ?? ''}
            onChange={e => setShootConfig(c => ({ ...c, product_focus: e.target.value }))}
            onBlur={e => handleConfigBlur('product_focus', e.target.value)}
            disabled={isActive} className={`${inputCls} resize-none`} />
        </Field>
        <Field label="Product Materials" className="mb-4">
          <textarea rows={2}
            value={shootConfig.product_materials ?? ''}
            onChange={e => setShootConfig(c => ({ ...c, product_materials: e.target.value }))}
            onBlur={e => handleConfigBlur('product_materials', e.target.value)}
            disabled={isActive} className={`${inputCls} resize-none`} />
        </Field>
        <Field label="Target Audience">
          <textarea rows={2}
            value={shootConfig.target_audience ?? ''}
            onChange={e => setShootConfig(c => ({ ...c, target_audience: e.target.value }))}
            onBlur={e => handleConfigBlur('target_audience', e.target.value)}
            disabled={isActive} className={`${inputCls} resize-none`} />
        </Field>
      </Section>

      {/* ── Start button ── */}
      {state === 'idle' && (
        <div className="flex justify-end">
          <button
            onClick={handleStart}
            disabled={!!nameError}
            className="flex items-center gap-2 bg-green-600 hover:bg-green-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium px-6 py-2.5 rounded-xl transition-colors shadow-lg shadow-green-900/20"
          >
            <Play size={14} /> Start Shoot
          </button>
        </div>
      )}

    </div>
  )
}

// ── Sub-components ─────────────────────────────────────────────────────────────

const inputCls = `w-full bg-[var(--c-surface-2)] border border-[var(--c-border-2)] rounded-lg px-3 py-2 text-sm text-[var(--c-text-1)] placeholder-[var(--c-text-4)] focus:outline-none focus:border-[var(--c-text-3)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed`

function SavedBadge({ visible, inline = false }) {
  if (!visible) return inline ? null : <div className="h-4 mt-2" />
  return (
    <div className={`flex items-center gap-1 text-xs text-green-400 transition-opacity ${inline ? '' : 'mt-2'}`}>
      <Check size={11} /> Saved
    </div>
  )
}

function Section({ title, icon, open, onToggle, disabled = false, children, className = '', badge }) {
  return (
    <div className={`bg-[var(--c-surface)] border border-[var(--c-border)] rounded-xl overflow-hidden ${disabled ? 'opacity-60' : ''} ${className}`}>
      <button
        onClick={disabled ? undefined : onToggle}
        disabled={disabled}
        className={`w-full flex items-center gap-2 px-5 py-3.5 text-left transition-colors border-b border-[var(--c-border)] ${disabled ? 'cursor-not-allowed' : 'hover:bg-[var(--c-surface-2)]'}`}
      >
        {icon && <span className="text-[var(--c-text-3)]">{icon}</span>}
        <span className="text-xs font-medium text-[var(--c-text-2)] uppercase tracking-wider flex-1">{title}</span>
        {badge}
        {open ? <ChevronUp size={13} className="text-[var(--c-text-4)]" /> : <ChevronDown size={13} className="text-[var(--c-text-4)]" />}
      </button>
      {open && <div className="p-5">{children}</div>}
    </div>
  )
}

function Field({ label, children, className = '' }) {
  return (
    <div className={className}>
      <label className="block text-xs text-[var(--c-text-3)] mb-1.5">{label}</label>
      {children}
    </div>
  )
}

function AssetSet({ label, target, files, onUpload, onDelete, disabled, flat = false }) {
  const inputRef = useRef(null)

  const handleDrop = (e) => {
    e.preventDefault()
    if (disabled) return
    const dropped = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'))
    if (dropped.length) onUpload(dropped)
  }

  return (
    <div>
      {label && !flat && (
        <p className="text-xs text-[var(--c-text-3)] font-medium mb-2">{label}</p>
      )}
      {files.length > 0 && (
        <div className={`grid gap-2 mb-3 ${flat ? 'grid-cols-4 sm:grid-cols-6' : 'grid-cols-3'}`}>
          {files.map(f => (
            <div key={f.filename} className="relative group aspect-square bg-[var(--c-surface-2)] rounded-lg overflow-hidden border border-[var(--c-border)]">
              <img src={f.url} alt={f.filename} className="w-full h-full object-cover"
                onError={e => { e.target.style.display = 'none' }} />
              <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-colors" />
              {!disabled && (
                <button
                  onClick={() => onDelete(f.filename)}
                  className="absolute top-1 right-1 w-5 h-5 rounded-full bg-red-500 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                  title={`Remove ${f.filename}`}
                >
                  <X size={10} />
                </button>
              )}
              <div className="absolute bottom-0 inset-x-0 p-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <p className="text-[9px] text-white truncate leading-none">{f.filename}</p>
              </div>
            </div>
          ))}
        </div>
      )}
      {!disabled && (
        <div
          onDragOver={e => e.preventDefault()}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className="flex flex-col items-center justify-center gap-1.5 border border-dashed border-[var(--c-border-2)] rounded-lg py-4 px-3 cursor-pointer hover:border-[var(--c-text-3)] hover:bg-[var(--c-surface-2)] transition-colors"
        >
          <Upload size={14} className="text-[var(--c-text-4)]" />
          <span className="text-xs text-[var(--c-text-4)]">
            {files.length > 0 ? 'Add more' : 'Upload images'}
          </span>
          <input ref={inputRef} type="file" multiple accept="image/*" className="hidden"
            onChange={e => { onUpload(e.target.files); e.target.value = '' }} />
        </div>
      )}
      {disabled && files.length === 0 && (
        <p className="text-xs text-[var(--c-text-4)] italic">No images</p>
      )}
    </div>
  )
}

function LogLine({ line }) {
  let cls = 'text-[var(--c-text-2)]'
  if (/error|failed|fatal/i.test(line))                      cls = 'text-red-400'
  else if (/warn|review/i.test(line))                        cls = 'text-yellow-400'
  else if (/✓|success|complete|done/i.test(line))            cls = 'text-green-400'
  else if (/^\[Monitor\]|^\[Phase/i.test(line))              cls = 'text-blue-400'
  else if (/^\[Image|^\[Photo|^\[Film|^\[Sprint/i.test(line)) cls = 'text-[var(--c-text-1b)]'
  return <div className={cls}>{line || ' '}</div>
}
