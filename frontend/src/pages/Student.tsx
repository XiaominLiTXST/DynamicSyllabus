import { useEffect, useState, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api'
import { fmtDate, fmtDateTime, groupByWeek, todayISO } from '../lib/format'
import type { Assessment, PublicView } from '../types'

const KIND_STYLES: Record<string, string> = {
  assignment: 'bg-sky-100 text-sky-800',
  quiz: 'bg-violet-100 text-violet-800',
  exam: 'bg-rose-100 text-rose-800',
}

export default function Student() {
  const { slug } = useParams<{ slug: string }>()
  const [view, setView] = useState<PublicView | null>(null)
  const [error, setError] = useState('')
  const [showAllAnnouncements, setShowAllAnnouncements] = useState(false)

  useEffect(() => {
    if (!slug) return
    api.getPublic(slug).then(setView).catch(() => setError('Syllabus not found.'))
  }, [slug])

  if (error) return <Centered>{error}</Centered>
  if (!view) return <Centered>Loading…</Centered>

  const today = todayISO()
  const weeks = groupByWeek(view.meetings)
  const announcementCutoff = view.next_class?.date ?? today
  const publishedAnnouncements = view.announcements
    .filter(
      (a) =>
        a.status === 'active' &&
        a.publish_date <= today &&
        a.publish_date <= announcementCutoff,
    )
    .sort((a, b) =>
      `${b.publish_date}-${b.created_at}`.localeCompare(`${a.publish_date}-${a.created_at}`),
    )
  const visibleAnnouncements = showAllAnnouncements
    ? publishedAnnouncements
    : publishedAnnouncements.slice(0, 2)
  const hiddenAnnouncementCount = publishedAnnouncements.length - visibleAnnouncements.length
  const assessmentsFor = (date: string, meetingId: number): Assessment[] =>
    view.assessments.filter(
      (a) => a.status === 'active' && (a.due_date === date || a.linked_meeting_id === meetingId),
    )

  return (
    <div className="min-h-screen bg-stone-50 text-stone-800">
      <div className="max-w-3xl mx-auto px-4 py-8">
        <header className="mb-6">
          <h1 className="text-2xl font-bold text-stone-900">{view.course.title}</h1>
          <p className="text-stone-500">
            {[view.course.term, view.course.instructor].filter(Boolean).join(' · ')}
          </p>
          <p className="text-xs text-stone-400 mt-1">Updated {fmtDateTime(view.updated_at)}</p>
        </header>

        <section className="space-y-3 mb-8">
          <div className="bg-white rounded-xl border border-stone-200 p-4">
            <h2 className="text-lg font-semibold text-stone-900 mb-1">Next class</h2>
            {view.next_class ? (
              <p className="text-stone-800">
                <span className="font-medium">{fmtDate(view.next_class.date)}</span>
                {view.next_class.title ? ` — ${view.next_class.title}` : ''}
              </p>
            ) : (
              <p className="text-stone-400">No upcoming classes.</p>
            )}
          </div>
          {view.upcoming_deadlines.map((a) => (
            <div key={a.id} className="bg-white rounded-xl border border-stone-200 p-4">
              <p className="text-stone-900">
                <span className="font-semibold">Deadline:</span>{' '}
                <span>{a.title} due {fmtDate(a.due_date)}</span>
                <span className={`ml-2 px-1.5 py-0.5 rounded text-xs ${KIND_STYLES[a.kind] ?? 'bg-stone-100 text-stone-700'}`}>
                  {a.kind}
                </span>
              </p>
            </div>
          ))}
          {view.upcoming_deadlines.length === 0 && (
            <div className="bg-white rounded-xl border border-stone-200 p-4">
              <p className="text-stone-400">No upcoming deadlines.</p>
            </div>
          )}
          {visibleAnnouncements.map((a) => (
            <div key={a.id} className="bg-white rounded-xl border border-stone-200 p-4">
              <p className="text-stone-900">
                <span className="font-semibold">Announcement:</span>{' '}
                <span className="font-medium">{a.title}</span>
              </p>
              <p className="text-sm text-stone-600 mt-1">{a.body}</p>
              <p className="text-xs text-stone-400 mt-1">{fmtDate(a.publish_date)}</p>
            </div>
          ))}
          {publishedAnnouncements.length === 0 && (
            <div className="bg-white rounded-xl border border-stone-200 p-4">
              <p className="text-stone-400">No announcements before the next class.</p>
            </div>
          )}
          {publishedAnnouncements.length > 2 && (
            <div className="flex justify-center pt-1">
              <button
                type="button"
                onClick={() => setShowAllAnnouncements((current) => !current)}
                className="min-w-44 rounded-lg border border-stone-300 bg-white px-5 py-2 text-sm font-medium text-stone-700 hover:bg-stone-50"
              >
                {showAllAnnouncements
                  ? 'View less'
                  : `View more${hiddenAnnouncementCount > 0 ? ` (${hiddenAnnouncementCount})` : ''}`}
              </button>
            </div>
          )}
        </section>

        <div className="space-y-6">
          {weeks.map(([weekKey, meetings], i) => (
            <section key={weekKey}>
              <h2 className="text-xs font-semibold uppercase tracking-wide text-stone-400 mb-2">
                Week {i + 1} · {fmtDate(weekKey)}
              </h2>
              <div className="space-y-2">
                {meetings.map((m) => {
                  const canceled = m.status === 'canceled'
                  const due = assessmentsFor(m.date, m.id)
                  const isToday = m.date === today
                  return (
                    <div
                      key={m.id}
                      className={`bg-white rounded-xl border p-3 ${
                        isToday ? 'border-amber-400 ring-1 ring-amber-200' : 'border-stone-200'
                      }`}
                    >
                      <div className="flex items-baseline gap-3">
                        <span className={`text-sm font-medium w-24 shrink-0 ${canceled ? 'text-stone-400 line-through' : 'text-stone-600'}`}>
                          {fmtDate(m.date)}
                        </span>
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className={`font-medium ${canceled ? 'text-stone-400 line-through' : 'text-stone-900'}`}>
                              {m.title || (m.topics.length ? m.topics.join(', ') : 'Class')}
                            </span>
                            {canceled && (
                              <span className="text-xs bg-stone-200 text-stone-600 px-1.5 py-0.5 rounded">Canceled</span>
                            )}
                          </div>
                          {!canceled && m.title && m.topics.length > 0 && (
                            <p className="text-sm text-stone-500">{m.topics.join(', ')}</p>
                          )}
                          {m.readings.map((r) => (
                            <p key={r.id} className="text-sm text-stone-500">
                              📖 {r.url ? (
                                <a href={r.url} className="underline" target="_blank" rel="noreferrer">{r.title}</a>
                              ) : (
                                r.title
                              )}
                            </p>
                          ))}
                          {due.map((a) => (
                            <p key={a.id} className="text-sm mt-1">
                              <span className={`px-1.5 py-0.5 rounded text-xs ${KIND_STYLES[a.kind] ?? ''}`}>{a.kind}</span>{' '}
                              <span className="text-stone-700">{a.title} due</span>
                            </p>
                          ))}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </section>
          ))}
        </div>
      </div>
    </div>
  )
}

function Centered({ children }: { children: ReactNode }) {
  return <div className="min-h-screen grid place-items-center text-stone-500">{children}</div>
}
