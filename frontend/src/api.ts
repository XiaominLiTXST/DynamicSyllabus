import type {
  Assessment,
  ChatResponse,
  CourseState,
  CourseSummary,
  DiffItem,
  Meeting,
  PublicView,
} from './types'

const TOKEN_KEY = 'syllabus_token'

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (t: string) => localStorage.setItem(TOKEN_KEY, t)
export const clearToken = () => localStorage.removeItem(TOKEN_KEY)

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(opts.headers as Record<string, string>),
  }
  const t = getToken()
  if (t) headers['Authorization'] = `Bearer ${t}`

  const res = await fetch(`/api${path}`, { ...opts, headers })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return null as T
  return res.json() as Promise<T>
}

const body = (data: unknown) => ({ body: JSON.stringify(data) })

export const api = {
  login: (password: string) =>
    req<{ token: string }>('/login', { method: 'POST', ...body({ password }) }),

  listCourses: () => req<CourseSummary[]>('/courses'),

  createCourse: (data: Record<string, unknown>) =>
    req<CourseState>('/courses', { method: 'POST', ...body(data) }),

  cloneCourse: (data: Record<string, unknown>) =>
    req<CourseState>('/courses/clone', { method: 'POST', ...body(data) }),

  getCourse: (id: number) => req<CourseState>(`/courses/${id}`),

  updateCourse: (id: number, data: Record<string, unknown>) =>
    req<CourseState>(`/courses/${id}`, { method: 'PATCH', ...body(data) }),

  deleteCourse: (id: number) =>
    req<{ ok: boolean }>(`/courses/${id}`, { method: 'DELETE' }),

  updateMeeting: (cid: number, mid: number, data: Partial<Meeting>) =>
    req<Meeting>(`/courses/${cid}/meetings/${mid}`, { method: 'PATCH', ...body(data) }),

  addReading: (cid: number, mid: number, data: Record<string, unknown>) =>
    req<Meeting>(`/courses/${cid}/meetings/${mid}/readings`, {
      method: 'POST',
      ...body(data),
    }),

  deleteReading: (cid: number, rid: number) =>
    req<{ ok: boolean }>(`/courses/${cid}/readings/${rid}`, { method: 'DELETE' }),

  addAssessment: (cid: number, data: Record<string, unknown>) =>
    req<Assessment>(`/courses/${cid}/assessments`, { method: 'POST', ...body(data) }),

  updateAssessment: (cid: number, aid: number, data: Partial<Assessment>) =>
    req<Assessment>(`/courses/${cid}/assessments/${aid}`, { method: 'PATCH', ...body(data) }),

  deleteAssessment: (cid: number, aid: number) =>
    req<{ ok: boolean }>(`/courses/${cid}/assessments/${aid}`, { method: 'DELETE' }),

  chat: (cid: number, message: string, history: { role: string; content: string }[]) =>
    req<ChatResponse>(`/courses/${cid}/chat`, { method: 'POST', ...body({ message, history }) }),

  apply: (cid: number, operations: Record<string, unknown>[], user_message: string) =>
    req<{ state: CourseState; diff: DiffItem[]; change_id: number }>(
      `/courses/${cid}/apply`,
      { method: 'POST', ...body({ operations, user_message }) },
    ),

  undo: (cid: number) =>
    req<{ state: CourseState; undone_change_id: number }>(`/courses/${cid}/undo`, {
      method: 'POST',
    }),

  getPublic: (token: string) => req<PublicView>(`/public/${token}`),
}
