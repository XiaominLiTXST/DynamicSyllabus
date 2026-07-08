import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { api, ApiError, clearToken, getToken } from '../api'
import ChatPanel from '../components/ChatPanel'
import CourseSetup from '../components/CourseSetup'
import Login from '../components/Login'
import SyllabusEditor from '../components/SyllabusEditor'
import type { CourseState, CourseSummary } from '../types'

export default function Instructor() {
  const [authed, setAuthed] = useState(!!getToken())
  const [courses, setCourses] = useState<CourseSummary[]>([])
  const [state, setState] = useState<CourseState | null>(null)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

  const handleAuthError = useCallback((err: unknown) => {
    if (err instanceof ApiError && err.status === 401) {
      clearToken()
      setAuthed(false)
    } else {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    }
  }, [])

  const loadCourses = useCallback(async () => {
    try {
      setCourses(await api.listCourses())
    } catch (err) {
      handleAuthError(err)
    }
  }, [handleAuthError])

  useEffect(() => {
    if (authed) loadCourses()
  }, [authed, loadCourses])

  const openCourse = useCallback(
    async (id: number) => {
      try {
        setState(await api.getCourse(id))
      } catch (err) {
        handleAuthError(err)
      }
    },
    [handleAuthError],
  )

  const deleteCourse = useCallback(
    async (course: CourseSummary) => {
      const confirmed = window.confirm(
        `Delete ${course.title}? This will permanently delete the course schedule, readings, assessments, assistant change history, and student link.`,
      )
      if (!confirmed) return
      try {
        await api.deleteCourse(course.id)
        setCourses((prev) => prev.filter((c) => c.id !== course.id))
      } catch (err) {
        handleAuthError(err)
      }
    },
    [handleAuthError],
  )

  const refresh = useCallback(async () => {
    if (!state) return
    try {
      setState(await api.getCourse(state.course.id))
    } catch (err) {
      handleAuthError(err)
    }
  }, [state, handleAuthError])

  if (!authed) return <Login onLogin={() => setAuthed(true)} />

  // Course list / creation screen.
  if (!state) {
    return (
      <div className="min-h-screen bg-stone-100">
        <Header onLogout={() => { clearToken(); setAuthed(false) }} />
        <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
          {error && <p className="text-red-600">{error}</p>}
          {courses.length > 0 && (
            <div className="bg-white rounded-2xl border border-stone-200 p-4">
              <h2 className="text-lg font-semibold text-stone-900 mb-3">Your courses</h2>
              <ul className="divide-y divide-stone-100">
                {courses.map((c) => (
                  <li key={c.id} className="flex items-center justify-between py-2">
                    <span className="text-stone-800">
                      {c.title} <span className="text-stone-400">· {c.term}</span>
                    </span>
                    <div className="flex items-center gap-3">
                      <button onClick={() => openCourse(c.id)} className="text-amber-700 hover:text-amber-900 text-sm font-medium">
                        Open →
                      </button>
                      <button onClick={() => deleteCourse(c)} className="text-red-600 hover:text-red-800 text-sm font-medium">
                        Delete
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <CourseSetup
            courses={courses}
            onCreated={(s) => {
              setState(s)
              loadCourses()
            }}
          />
        </div>
      </div>
    )
  }

  // Editor screen.
  const shareUrl = `${location.origin}/s/${state.course.public_token}`
  return (
    <div className="min-h-screen bg-stone-100 flex flex-col">
      <Header
        onLogout={() => { clearToken(); setAuthed(false) }}
        onBack={() => { setState(null); loadCourses() }}
        title={`${state.course.title}${state.course.term ? ` · ${state.course.term}` : ''}`}
        right={
          <button
            onClick={() => {
              navigator.clipboard.writeText(shareUrl)
              setCopied(true)
              setTimeout(() => setCopied(false), 1500)
            }}
            className="text-sm bg-stone-800 text-white rounded-lg px-3 py-1.5 hover:bg-stone-900"
          >
            {copied ? 'Link copied ✓' : 'Copy student link ⧉'}
          </button>
        }
      />
      <div className="flex-1 max-w-7xl w-full mx-auto px-4 py-6 grid lg:grid-cols-[1fr_22rem] gap-6">
        <div className="overflow-y-auto">
          <SyllabusEditor state={state} onChange={refresh} />
        </div>
        <div className="lg:sticky lg:top-6 h-[calc(100vh-7rem)]">
          <ChatPanel courseId={state.course.id} onApplied={setState} />
        </div>
      </div>
    </div>
  )
}

function Header({
  title,
  right,
  onBack,
  onLogout,
}: {
  title?: string
  right?: ReactNode
  onBack?: () => void
  onLogout: () => void
}) {
  return (
    <header className="bg-white border-b border-stone-200 px-4 py-3 flex items-center gap-3">
      {onBack && (
        <button onClick={onBack} className="text-stone-500 hover:text-stone-800 text-sm">
          ← All courses
        </button>
      )}
      <h1 className="font-semibold text-stone-900 flex-1">{title ?? 'Interactive Syllabus'}</h1>
      {right}
      <button onClick={onLogout} className="text-sm text-stone-500 hover:text-stone-800">
        Sign out
      </button>
    </header>
  )
}
