import { useState, type FormEvent } from 'react'
import { api } from '../api'
import type { CourseState, CourseSummary } from '../types'

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

export default function CourseSetup({
  courses,
  onCreated,
}: {
  courses: CourseSummary[]
  onCreated: (s: CourseState) => void
}) {
  const [sourceId, setSourceId] = useState('')
  const [title, setTitle] = useState('')
  const [term, setTerm] = useState('')
  const [instructor, setInstructor] = useState('')
  const [days, setDays] = useState<string[]>(['Mon', 'Wed'])
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [excluded, setExcluded] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  function toggleDay(d: string) {
    setDays((prev) => (prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d]))
  }

  function selectSource(id: string) {
    setSourceId(id)
    const course = courses.find((c) => String(c.id) === id)
    if (course) {
      setTitle((current) => current || `${course.title} Copy`)
      setTerm((current) => current || course.term)
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    if (!title || !start || !end || days.length === 0) {
      setError('Title, meeting days, and start/end dates are required.')
      return
    }
    setBusy(true)
    try {
      const excludedDates = excluded
        .split(/[\s,]+/)
        .map((s) => s.trim())
        .filter(Boolean)
      const payload = {
        title,
        term,
        instructor,
        meeting_days: days,
        start_date: start,
        end_date: end,
        excluded_dates: excludedDates,
      }
      const state = sourceId
        ? await api.cloneCourse({ ...payload, source_course_id: Number(sourceId) })
        : await api.createCourse(payload)
      onCreated(state)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create course.')
    } finally {
      setBusy(false)
    }
  }

  const field = 'w-full border border-stone-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-amber-600/40'

  return (
    <form onSubmit={submit} className="bg-white rounded-2xl border border-stone-200 p-6 max-w-xl">
      <h2 className="text-lg font-semibold text-stone-900 mb-4">New course</h2>
      <div className="space-y-3">
        {courses.length > 0 && (
          <label className="block text-sm text-stone-600">
            Start from
            <select className={`${field} mt-1`} value={sourceId} onChange={(e) => selectSource(e.target.value)}>
              <option value="">Blank course</option>
              {courses.map((course) => (
                <option key={course.id} value={course.id}>
                  Copy {course.title}{course.term ? ` · ${course.term}` : ''}
                </option>
              ))}
            </select>
          </label>
        )}
        <input className={field} placeholder="Course title (e.g. CS 250 Data Structures)" value={title} onChange={(e) => setTitle(e.target.value)} />
        <div className="flex gap-3">
          <input className={field} placeholder="Term (Fall 2026)" value={term} onChange={(e) => setTerm(e.target.value)} />
          <input className={field} placeholder="Instructor" value={instructor} onChange={(e) => setInstructor(e.target.value)} />
        </div>
        <div>
          <label className="block text-sm text-stone-600 mb-1">Meeting days</label>
          <div className="flex gap-1 flex-wrap">
            {DAYS.map((d) => (
              <button
                type="button"
                key={d}
                onClick={() => toggleDay(d)}
                className={`px-3 py-1.5 rounded-lg text-sm border ${
                  days.includes(d)
                    ? 'bg-amber-700 text-white border-amber-700'
                    : 'bg-white text-stone-600 border-stone-300'
                }`}
              >
                {d}
              </button>
            ))}
          </div>
        </div>
        <div className="flex gap-3">
          <label className="flex-1 text-sm text-stone-600">
            Start date
            <input type="date" className={field} value={start} onChange={(e) => setStart(e.target.value)} />
          </label>
          <label className="flex-1 text-sm text-stone-600">
            End date
            <input type="date" className={field} value={end} onChange={(e) => setEnd(e.target.value)} />
          </label>
        </div>
        <label className="block text-sm text-stone-600">
          Excluded dates (holidays/breaks — ISO dates, space or comma separated)
          <textarea className={field} rows={2} placeholder="2026-11-25 2026-11-27" value={excluded} onChange={(e) => setExcluded(e.target.value)} />
        </label>
        {sourceId && (
          <p className="text-sm text-stone-500">
            The selected course's meetings, readings, and assessments will be copied onto the new schedule by meeting position.
          </p>
        )}
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button disabled={busy} className="bg-amber-700 text-white rounded-lg px-4 py-2 font-medium hover:bg-amber-800 disabled:opacity-50">
          {busy ? 'Creating…' : 'Create course & generate schedule'}
        </button>
      </div>
    </form>
  )
}
