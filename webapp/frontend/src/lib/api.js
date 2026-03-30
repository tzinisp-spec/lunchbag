const BASE = '/api'

async function get(path) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

export const api = {
  dashboard:   ()         => get('/dashboard'),
  shoots:      ()         => get('/shoots'),
  shoot:       (id)       => get(`/shoots/${id}`),
  agents:      ()         => get('/agents'),
  imageUrl:    (path)     => `${BASE}/image?path=${encodeURIComponent(path)}`,
}
