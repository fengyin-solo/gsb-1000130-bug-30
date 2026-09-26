/** 统一请求封装：拼后端地址、抛网络错误、给页脚留一句可读的说明。 */
const API_BASE = import.meta.env.VITE_API_BASE ?? ''

export function request(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  return fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  }).catch((error: unknown) => {
    const detail = error instanceof Error ? error.message : '请求未送达'
    throw new Error(`接口请求失败：${detail}`)
  })
}

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await request(path)
  if (!response.ok) {
    throw new Error(`接口返回 ${response.status}，数据未更新`)
  }
  return (await response.json()) as T
}

/** 读取响应体；接口异常时体可能不是 JSON，解析失败按空处理而不是再抛一次。 */
export async function readPayload(response: Response): Promise<Record<string, unknown> | null> {
  try {
    return (await response.json()) as Record<string, unknown>
  } catch {
    return null
  }
}

/** 从响应体里挑一句可读的说明：优先 FastAPI 的 detail，其次业务约定的 message。 */
export function payloadMessage(payload: Record<string, unknown> | null): string | null {
  if (!payload) {
    return null
  }
  const detail = payload.detail
  if (typeof detail === 'string' && detail) {
    return detail
  }
  const message = payload.message
  if (typeof message === 'string' && message) {
    return message
  }
  return null
}
