const BASE = '/api'

const FETCH_OPTS = { credentials: 'include' }

async function get(path) {
  const res = await fetch(`${BASE}${path}`, FETCH_OPTS)
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    ...FETCH_OPTS,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

async function del(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    ...FETCH_OPTS,
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

async function patch(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    ...FETCH_OPTS,
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

async function upload(path, formData) {
  const res = await fetch(`${BASE}${path}`, { ...FETCH_OPTS, method: 'POST', body: formData })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

export const api = {
  // Auth
  authMe:         ()                    => get('/auth/me'),
  authLogin:      (username, password)  => post('/auth/login', { username, password }),
  authLogout:     ()                    => post('/auth/logout', {}),

  search:         (q)                   => get(`/search?q=${encodeURIComponent(q)}`),
  dashboard:      ()                    => get('/dashboard'),
  shoots:         ()                    => get('/shoots'),
  shoot:          (id)                  => get(`/shoots/${id}`),
  agents:         ()                    => get('/agents'),
  imageUrl:       (path)                => `${BASE}/image?path=${encodeURIComponent(path)}`,
  approveImages:  (shootId, filenames)  => post(`/shoots/${shootId}/images/approve`, { filenames }),
  deleteImages:   (shootId, filenames)  => post(`/shoots/${shootId}/images/delete`,  { filenames }),
  contentPosts:   ()                    => get('/content/posts'),
  updatePost:     (slot, body)          => patch(`/content/posts/${slot}`, body),
  deletePosts:    (slots)               => del('/content/posts', { slots }),
  activity:       ()                    => get('/activity'),
  logs:           (lines = 500)         => get(`/logs?lines=${lines}`),
  status:         ()                    => get('/status'),
  photoshootReport:   ()                => get('/photoshoot-report'),
  contentPlanReport:  ()                => get('/content-plan-report'),
  brand:          ()                    => get('/brand'),
  concept:        ()                    => get('/concept'),
  products:       ()                    => get('/products'),

  // Run management
  runStatus:      ()                    => get('/run/status'),
  runStart:       (config)              => post('/run/start', { config }),
  runStop:        ()                    => post('/run/stop', {}),
  runPause:       ()                    => post('/run/pause', {}),
  runResume:      ()                    => post('/run/resume', {}),
  runLogsUrl:     ()                    => `${BASE}/run/logs/stream`,

  // Phase 2 — Content Pipeline
  p2Status:      ()                    => get('/p2/status'),
  p2Start:       (body)                => post('/p2/start', body),
  p2Stop:        ()                    => post('/p2/stop', {}),
  p2Pause:       ()                    => post('/p2/pause', {}),
  p2Resume:      ()                    => post('/p2/resume', {}),
  p2LogsUrl:     ()                    => `${BASE}/p2/logs/stream`,
  p2Shoots:      ()                    => get('/p2/shoots'),

  // Asset management
  runAssets:      ()                    => get('/run/assets'),
  runUpload:      (target, files)       => {
    const fd = new FormData()
    fd.append('target', target)
    files.forEach(f => fd.append('files', f))
    return upload('/run/upload', fd)
  },
  runDeleteAsset:   (target, filename)    => post('/run/delete-asset', { target, filename }),
  runValidateName:  (name, season)        => get(`/run/validate-name?name=${encodeURIComponent(name)}&season=${encodeURIComponent(season)}`),
  runConfigGet:     ()                    => get('/run/config'),
  runConfigSave:    (config)              => post('/run/config', config),
  conceptSave:      (text)               => post('/concept', { text }),
}
