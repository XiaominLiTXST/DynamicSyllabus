import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../api'
import { fmtDate, groupByWeek } from '../lib/format'
import type { Assessment, CourseMeta, CourseState, Meeting } from '../types'

const KIND_STYLES: Record<string, string> = {
  assignment: 'bg-sky-100 text-sky-800',
  quiz: 'bg-violet-100 text-violet-800',
  exam: 'bg-rose-100 text-rose-800',
}

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

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
    <form onSubmit={submit} className="bg-white rounded-2xl border border-stone-200 p-4">
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
    <div className="bg-white rounded-2xl border border-stone-200 p-4">
      <h3 className="font-semibold text-stone-900 mb-3">Assessments</h3>
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
      <div className="flex gap-2 items-center border-t border-stone-100 pt-3">
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
      <CourseInfoSection course={state.course} onChange={onChange} />
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
      <AssessmentsSection cid={cid} assessments={state.assessments} onChange={onChange} />
    </div>
  )
}
