import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../api'
import { fmtDate, groupByWeek } from '../lib/format'
import type { Announcement, Assessment, CourseMeta, CourseState, Meeting } from '../types'

const KIND_STYLES: Record<string, string> = {
  assignment: 'bg-sky-100 text-sky-800',
  quiz: 'bg-violet-100 text-violet-800',
  exam: 'bg-rose-100 text-rose-800',
}

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
type ToolTab = 'assignment' | 'announcement' | 'course'

function CourseInfoSection({
  course,
  onChange,
}: {
  course: CourseMeta
  onChange: () => void
}) {
  const [title, setTitle] = useState(course.title)
  const [term, setTerm] = useState(course.term)
  const [instructor, setInstructor] = useState(course.instructor)
  const [timezone, setTimezone] = useState(course.timezone)
  const [days, setDays] = useState<string[]>(course.meeting_days)
  const [start, setStart] = useState(course.start_date)
  const [end, setEnd] = useState(course.end_date)
  const [excluded, setExcluded] = useState(course.excluded_dates.join(' '))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setTitle(course.title)
    setTerm(course.term)
    setInstructor(course.instructor)
    setTimezone(course.timezone)
    setDays(course.meeting_days)
    setStart(course.start_date)
    setEnd(course.end_date)
    setExcluded(course.excluded_dates.join(' '))
  }, [course])

  function toggleDay(day: string) {
    setDays((prev) => (prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day]))
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    if (!title.trim() || !start || !end || days.length === 0) {
      setError('Title, meeting days, and start/end dates are required.')
      return
    }
    const excludedDates = excluded
      .split(/[\s,]+/)
      .map((s) => s.trim())
      .filter(Boolean)
    const scheduleChanged =
      start !== course.start_date ||
      end !== course.end_date ||
      days.join('|') !== course.meeting_days.join('|') ||
      excludedDates.join('|') !== course.excluded_dates.join('|')
    if (
      scheduleChanged &&
      !window.confirm(
        'Changing dates, meeting days, or excluded dates rebuilds the meeting grid. Existing meeting content is preserved by position, but meetings outside the new schedule will be deleted.',
      )
    ) {
      return
    }
    setBusy(true)
    try {
      await api.updateCourse(course.id, {
        title: title.trim(),
        term,
        instructor,
        timezone,
        meeting_days: days,
        start_date: start,
        end_date: end,
        excluded_dates: excludedDates,
      })
      onChange()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update course.')
    } finally {
      setBusy(false)
    }
  }

  const field = 'border border-stone-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-600/40'

  return (
    <form onSubmit={submit}>
      <div className="flex items-center justify-between gap-3 mb-3">
        <h3 className="font-semibold text-stone-900">Course details</h3>
        <button disabled={busy} className="bg-stone-800 text-white rounded-lg px-3 py-1.5 text-sm hover:bg-stone-900 disabled:opacity-50">
          {busy ? 'Saving...' : 'Save details'}
        </button>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <input className={field} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Course title" />
        <input className={field} value={term} onChange={(e) => setTerm(e.target.value)} placeholder="Term" />
        <input className={field} value={instructor} onChange={(e) => setInstructor(e.target.value)} placeholder="Instructor" />
        <input className={field} value={timezone} onChange={(e) => setTimezone(e.target.value)} placeholder="Timezone" />
      </div>
      <div className="grid gap-3 md:grid-cols-2 mt-3">
        <label className="text-sm text-stone-600">
          Start date
          <input type="date" className={`w-full mt-1 ${field}`} value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label className="text-sm text-stone-600">
          End date
          <input type="date" className={`w-full mt-1 ${field}`} value={end} onChange={(e) => setEnd(e.target.value)} />
        </label>
      </div>
      <div className="mt-3">
        <p className="text-sm text-stone-600 mb-1">Meeting days</p>
        <div className="flex gap-1 flex-wrap">
          {DAYS.map((day) => (
            <button
              type="button"
              key={day}
              onClick={() => toggleDay(day)}
              className={`px-3 py-1.5 rounded-lg text-sm border ${
                days.includes(day)
                  ? 'bg-amber-700 text-white border-amber-700'
                  : 'bg-white text-stone-600 border-stone-300'
              }`}
            >
              {day}
            </button>
          ))}
        </div>
      </div>
      <label className="block text-sm text-stone-600 mt-3">
        Excluded dates
        <textarea className={`w-full mt-1 ${field}`} rows={2} value={excluded} onChange={(e) => setExcluded(e.target.value)} placeholder="2026-11-25 2026-11-27" />
      </label>
      {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
    </form>
  )
}

function MeetingCard({
  cid,
  meeting,
  onChange,
}: {
  cid: number
  meeting: Meeting
  onChange: () => void
}) {
  const [newReading, setNewReading] = useState('')
  const canceled = meeting.status === 'canceled'

  async function save(data: Partial<Meeting>) {
    await api.updateMeeting(cid, meeting.id, data)
    onChange()
  }

  async function addReading() {
    if (!newReading.trim()) return
    await api.addReading(cid, meeting.id, { title: newReading.trim() })
    setNewReading('')
    onChange()
  }

  return (
    <div className={`rounded-xl border p-3 ${canceled ? 'border-stone-200 bg-stone-50' : 'border-stone-200 bg-white'}`}>
      <div className="flex items-center justify-between mb-2">
        <span className={`text-sm font-medium ${canceled ? 'text-stone-400 line-through' : 'text-stone-700'}`}>
          {fmtDate(meeting.date)}
        </span>
        <button
          onClick={() => save({ status: canceled ? 'scheduled' : 'canceled' })}
          className="text-xs text-stone-500 hover:text-stone-800"
        >
          {canceled ? 'Restore' : 'Cancel'}
        </button>
      </div>
      <input
        defaultValue={meeting.title ?? ''}
        placeholder="Lecture title"
        onBlur={(e) => e.target.value !== (meeting.title ?? '') && save({ title: e.target.value })}
        className="w-full font-medium text-stone-900 mb-1 px-1 py-0.5 rounded hover:bg-stone-50 focus:bg-stone-50 focus:outline-none"
      />
      <input
        defaultValue={meeting.topics.join(', ')}
        placeholder="Topics (comma separated)"
        onBlur={(e) => {
          const topics = e.target.value.split(',').map((s) => s.trim()).filter(Boolean)
          if (topics.join('|') !== meeting.topics.join('|')) save({ topics })
        }}
        className="w-full text-sm text-stone-600 px-1 py-0.5 rounded hover:bg-stone-50 focus:bg-stone-50 focus:outline-none"
      />
      <div className="mt-2 space-y-1">
        {meeting.readings.map((r) => (
          <div key={r.id} className="flex items-center gap-2 text-sm text-stone-600">
            <span>📖 {r.title}</span>
            <button
              onClick={async () => {
                await api.deleteReading(cid, r.id)
                onChange()
              }}
              className="text-stone-400 hover:text-red-600 text-xs"
            >
              ✕
            </button>
          </div>
        ))}
        <div className="flex gap-1">
          <input
            value={newReading}
            onChange={(e) => setNewReading(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addReading()}
            placeholder="+ reading"
            className="text-sm border border-stone-200 rounded px-2 py-0.5 flex-1 focus:outline-none focus:ring-1 focus:ring-amber-600/40"
          />
        </div>
      </div>
    </div>
  )
}

function AssessmentsSection({
  cid,
  assessments,
  onChange,
}: {
  cid: number
  assessments: Assessment[]
  onChange: () => void
}) {
  const [kind, setKind] = useState('assignment')
  const [title, setTitle] = useState('')
  const [due, setDue] = useState('')

  async function add() {
    if (!title.trim() || !due) return
    await api.addAssessment(cid, { kind, title: title.trim(), due_date: due })
    setTitle('')
    setDue('')
    onChange()
  }

  return (
    <div>
      <h3 className="font-semibold text-stone-900 mb-3">New assignment</h3>
      <div className="space-y-2 mb-4">
        {assessments.map((a) => (
          <div key={a.id} className="flex items-center gap-2 text-sm">
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${KIND_STYLES[a.kind] ?? 'bg-stone-100 text-stone-700'}`}>
              {a.kind}
            </span>
            <span className={`flex-1 ${a.status === 'canceled' ? 'line-through text-stone-400' : 'text-stone-800'}`}>{a.title}</span>
            <input
              type="date"
              defaultValue={a.due_date}
              onBlur={(e) => e.target.value !== a.due_date && api.updateAssessment(cid, a.id, { due_date: e.target.value }).then(onChange)}
              className="border border-stone-200 rounded px-2 py-0.5 text-stone-600"
            />
            <button
              onClick={async () => {
                await api.deleteAssessment(cid, a.id)
                onChange()
              }}
              className="text-stone-400 hover:text-red-600"
            >
              ✕
            </button>
          </div>
        ))}
        {assessments.length === 0 && <p className="text-sm text-stone-400">No assessments yet.</p>}
      </div>
      <div className="flex flex-col gap-2 border-t border-stone-100 pt-3 md:flex-row md:items-center">
        <select value={kind} onChange={(e) => setKind(e.target.value)} className="border border-stone-300 rounded-lg px-2 py-1.5 text-sm">
          <option value="assignment">Assignment</option>
          <option value="quiz">Quiz</option>
          <option value="exam">Exam</option>
        </select>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title" className="flex-1 border border-stone-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-amber-600/40" />
        <input type="date" value={due} onChange={(e) => setDue(e.target.value)} className="border border-stone-300 rounded-lg px-2 py-1.5 text-sm" />
        <button onClick={add} className="bg-amber-700 text-white rounded-lg px-3 py-1.5 text-sm hover:bg-amber-800">
          Add
        </button>
      </div>
    </div>
  )
}

function AnnouncementsSection({
  cid,
  announcements,
  onChange,
}: {
  cid: number
  announcements: Announcement[]
  onChange: () => void
}) {
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [publishDate, setPublishDate] = useState(new Date().toISOString().slice(0, 10))
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [editBody, setEditBody] = useState('')
  const [editPublishDate, setEditPublishDate] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function add(e: FormEvent) {
    e.preventDefault()
    setError('')
    if (!title.trim() || !body.trim() || !publishDate) {
      setError('Title, message, and publish date are required.')
      return
    }
    setBusy(true)
    try {
      await api.addAnnouncement(cid, {
        title: title.trim(),
        body: body.trim(),
        publish_date: publishDate,
      })
      setTitle('')
      setBody('')
      onChange()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add announcement.')
    } finally {
      setBusy(false)
    }
  }

  function startEdit(announcement: Announcement) {
    setEditingId(announcement.id)
    setEditTitle(announcement.title)
    setEditBody(announcement.body)
    setEditPublishDate(announcement.publish_date)
    setError('')
  }

  function cancelEdit() {
    setEditingId(null)
    setEditTitle('')
    setEditBody('')
    setEditPublishDate('')
  }

  async function saveEdit(announcement: Announcement) {
    setError('')
    if (!editTitle.trim() || !editBody.trim() || !editPublishDate) {
      setError('Title, message, and publish date are required.')
      return
    }
    setBusy(true)
    try {
      await api.updateAnnouncement(cid, announcement.id, {
        title: editTitle.trim(),
        body: editBody.trim(),
        publish_date: editPublishDate,
      })
      cancelEdit()
      onChange()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update announcement.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <h3 className="font-semibold text-stone-900 mb-3">Announcement</h3>
      <form onSubmit={add} className="space-y-3">
        <div className="grid gap-3 md:grid-cols-[1fr_11rem]">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Announcement title"
            className="border border-stone-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-600/40"
          />
          <input
            type="date"
            value={publishDate}
            onChange={(e) => setPublishDate(e.target.value)}
            className="border border-stone-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-600/40"
          />
        </div>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Write the message students should see."
          rows={3}
          className="w-full border border-stone-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-600/40"
        />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button disabled={busy} className="bg-amber-700 text-white rounded-lg px-3 py-1.5 text-sm hover:bg-amber-800 disabled:opacity-50">
          {busy ? 'Posting...' : 'Post announcement'}
        </button>
      </form>
      <div className="border-t border-stone-100 mt-4 pt-3 space-y-2">
        {announcements.map((announcement) => (
          <div key={announcement.id} className="flex items-start gap-3 text-sm">
            {editingId === announcement.id ? (
              <div className="flex-1 space-y-2">
                <div className="grid gap-2 md:grid-cols-[1fr_11rem]">
                  <input
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    className="border border-stone-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-amber-600/40"
                  />
                  <input
                    type="date"
                    value={editPublishDate}
                    onChange={(e) => setEditPublishDate(e.target.value)}
                    className="border border-stone-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-amber-600/40"
                  />
                </div>
                <textarea
                  value={editBody}
                  onChange={(e) => setEditBody(e.target.value)}
                  rows={3}
                  className="w-full border border-stone-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-amber-600/40"
                />
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => saveEdit(announcement)}
                    className="bg-amber-700 text-white rounded-lg px-3 py-1.5 text-xs hover:bg-amber-800 disabled:opacity-50"
                  >
                    Save
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={cancelEdit}
                    className="bg-white border border-stone-300 text-stone-700 rounded-lg px-3 py-1.5 text-xs hover:bg-stone-50"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`font-medium ${announcement.status === 'archived' ? 'text-stone-400 line-through' : 'text-stone-900'}`}>
                      {announcement.title}
                    </span>
                    <span className="text-xs text-stone-400">{fmtDate(announcement.publish_date)}</span>
                  </div>
                  <p className={announcement.status === 'archived' ? 'text-stone-400' : 'text-stone-600'}>
                    {announcement.body}
                  </p>
                </div>
                <button
                  onClick={() => startEdit(announcement)}
                  className="text-xs text-amber-700 hover:text-amber-900"
                >
                  Edit
                </button>
                <button
                  onClick={async () => {
                    await api.updateAnnouncement(cid, announcement.id, {
                      status: announcement.status === 'archived' ? 'active' : 'archived',
                    })
                    onChange()
                  }}
                  className="text-xs text-stone-500 hover:text-stone-800"
                >
                  {announcement.status === 'archived' ? 'Restore' : 'Archive'}
                </button>
                <button
                  onClick={async () => {
                    if (!window.confirm(`Delete announcement "${announcement.title}"?`)) return
                    await api.deleteAnnouncement(cid, announcement.id)
                    onChange()
                  }}
                  className="text-xs text-red-600 hover:text-red-800"
                >
                  Delete
                </button>
              </>
            )}
          </div>
        ))}
        {announcements.length === 0 && <p className="text-sm text-stone-400">No announcements yet.</p>}
      </div>
    </div>
  )
}

function CourseTools({
  state,
  onChange,
}: {
  state: CourseState
  onChange: () => void
}) {
  const [tab, setTab] = useState<ToolTab>('assignment')
  const tabs: { id: ToolTab; label: string }[] = [
    { id: 'assignment', label: 'New Assignment' },
    { id: 'announcement', label: 'Announcement' },
    { id: 'course', label: 'Edit Course' },
  ]

  return (
    <div className="bg-white rounded-2xl border border-stone-200 overflow-hidden">
      <div className="flex flex-wrap border-b border-stone-200">
        {tabs.map((item) => (
          <button
            type="button"
            key={item.id}
            onClick={() => setTab(item.id)}
            className={`px-4 py-3 text-sm font-semibold border-r border-stone-200 ${
              tab === item.id
                ? 'bg-amber-700 text-white'
                : 'bg-amber-50 text-stone-700 hover:bg-amber-100'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="p-4">
        {tab === 'assignment' && (
          <AssessmentsSection
            cid={state.course.id}
            assessments={state.assessments}
            onChange={onChange}
          />
        )}
        {tab === 'announcement' && (
          <AnnouncementsSection
            cid={state.course.id}
            announcements={state.announcements}
            onChange={onChange}
          />
        )}
        {tab === 'course' && (
          <CourseInfoSection course={state.course} onChange={onChange} />
        )}
      </div>
    </div>
  )
}

export default function SyllabusEditor({
  state,
  onChange,
}: {
  state: CourseState
  onChange: () => void
}) {
  const cid = state.course.id
  const weeks = groupByWeek(state.meetings)

  return (
    <div className="space-y-5">
      <CourseTools state={state} onChange={onChange} />
      {weeks.map(([weekKey, meetings], i) => (
        <div key={weekKey}>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-stone-400 mb-2">
            Week {i + 1} · {fmtDate(weekKey)}
          </h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {meetings.map((m) => (
              <MeetingCard key={m.id} cid={cid} meeting={m} onChange={onChange} />
            ))}
          </div>
        </div>
      ))}
      {state.meetings.length === 0 && (
        <p className="text-stone-500">No meetings — check the course dates and meeting days.</p>
      )}
    </div>
  )
}
