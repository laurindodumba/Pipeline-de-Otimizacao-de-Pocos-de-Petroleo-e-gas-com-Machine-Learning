const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
).replace(/\/+$/, '')

async function request(path, options) {
  const response = await fetch(`${API_BASE_URL}${path}`, options)
  const result = await response.json()
  if (!response.ok) {
    const detail = result.detail
    const message = Array.isArray(detail)
      ? detail.map((issue) => issue.msg).join('; ')
      : detail || 'Não foi possível gerar a estimativa.'
    throw new Error(message)
  }

  return result
}

export function getDashboardSummary() {
  return request('/dashboard/summary')
}

export function predictDailyMargin(input) {
  return request('/predict', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(input),
  })
}
