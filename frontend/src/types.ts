export interface Reading {
  id: number
  title: string
  citation: string | null
  url: string | null
  required: boolean
}

export interface Meeting {
  id: number
  date: string // ISO
  position: number
  title: string | null
  status: string // "scheduled" | "canceled"
  location: string | null
  notes: string | null
  topics: string[]
  readings: Reading[]
}

export interface Assessment {
  id: number
  kind: string // assignment | quiz | exam
  title: string
  due_date: string // ISO
  linked_meeting_id: number | null
  description: string | null
  status: string // active | canceled
}

export interface Announcement {
  id: number
  title: string
  body: string
  publish_date: string // ISO
  status: string // active | archived
  created_at: string
  updated_at: string
}

export interface CourseMeta {
  id: number
  title: string
  term: string
  instructor: string
  timezone: string
  meeting_days: string[]
  start_date: string
  end_date: string
  excluded_dates: string[]
  public_token?: string
}

export interface CourseState {
  course: CourseMeta
  meetings: Meeting[]
  assessments: Assessment[]
  announcements: Announcement[]
}

export interface DiffItem {
  type: string
  summary: string
}

export interface ChatResponse {
  explanation: string
  needs_clarification: string | null
  operations: Record<string, unknown>[]
  diff: DiffItem[]
  apply_error: string | null
}

export interface PublicView {
  course: CourseMeta
  meetings: Meeting[]
  assessments: Assessment[]
  announcements: Announcement[]
  upcoming_deadlines: Assessment[]
  latest_announcements: Announcement[]
  next_class: Meeting | null
  updated_at: string
}

export interface CourseSummary {
  id: number
  title: string
  term: string
  public_token: string
  updated_at: string
}
