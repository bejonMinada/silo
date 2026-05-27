const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

function parseErrorPayload(data, fallback) {
  if (data?.error?.message) return data.error.message
  if (data?.detail) return data.detail
  return fallback
}

export async function apiRequest(path, { method = 'GET', token, body } = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  })

  const contentType = response.headers.get('content-type') || ''
  const data = contentType.includes('application/json') ? await response.json().catch(() => null) : await response.text()

  if (!response.ok) {
    const fallback = `Request failed: ${response.status}`
    throw new Error(parseErrorPayload(data, fallback))
  }

  return data
}
