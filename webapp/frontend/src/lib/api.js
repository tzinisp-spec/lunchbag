const BASE = '/api'

async function get(path) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

export const api = {
  dashboard:      ()                    => get('/dashboard'),
  shoots:         ()                    => get('/shoots'),
  shoot:          (id)                  => get(`/shoots/${id}`),
  agents:         ()                    => get('/agents'),
  imageUrl:       (path)                => `${BASE}/image?path=${encodeURIComponent(path)}`,
  approveImages:  (shootId, filenames)  => post(`/shoots/${shootId}/images/approve`, { filenames }),
  deleteImages:   (shootId, filenames)  => post(`/shoots/${shootId}/images/delete`,  { filenames }),
}
