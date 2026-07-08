import { useState, type FormEvent } from 'react'
import { api } from '../api'
import type { ChatResponse, CourseState } from '../types'

interface Turn {
  role: 'user' | 'assistant'
  content: string
}

const EXAMPLES = [
  'Delay all class topics by one week.',
  'Add a quiz after the recursion lecture.',
  'Cancel the class on the second meeting and adjust the schedule.',
]

export default function ChatPanel({
  courseId,
  onApplied,
}: {
  courseId: number
  onApplied: (s: CourseState) => void
}) {
  const [input, setInput] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [proposal, setProposal] = useState<ChatResponse | null>(null)
  const [lastUserMsg, setLastUserMsg] = useState('')
  const [busy, setBusy] = useState(false)

  async function send(e?: FormEvent) {
    e?.preventDefault()
    const message = input.trim()
    if (!message || busy) return
    setBusy(true)
    setProposal(null)
    const history = turns.map((t) => ({ role: t.role, content: t.content }))
    setTurns((t) => [...t, { role: 'user', content: message }])
    setLastUserMsg(message)
    setInput('')
    try {
      const res = await api.chat(courseId, message, history)
      const assistantText =
        res.needs_clarification ||
        res.apply_error ||
        res.explanation ||
        (res.operations.length ? 'Proposed changes — review below.' : 'No changes proposed.')
      setTurns((t) => [...t, { role: 'assistant', content: assistantText }])
      const actionable = res.operations.length > 0 && !res.needs_clarification && !res.apply_error
      setProposal(actionable ? res : null)
    } catch (err) {
      setTurns((t) => [
        ...t,
        { role: 'assistant', content: err instanceof Error ? err.message : 'Request failed.' },
      ])
    } finally {
      setBusy(false)
    }
  }

  async function confirm() {
    if (!proposal) return
    setBusy(true)
    try {
      const res = await api.apply(courseId, proposal.operations, lastUserMsg)
      onApplied(res.state)
      setTurns((t) => [...t, { role: 'assistant', content: `Applied ${res.diff.length} change(s).` }])
      setProposal(null)
    } catch (err) {
      setTurns((t) => [
        ...t,
        { role: 'assistant', content: err instanceof Error ? err.message : 'Apply failed.' },
      ])
    } finally {
      setBusy(false)
    }
  }

  function discard() {
    setProposal(null)
    setTurns((t) => [...t, { role: 'assistant', content: 'Discarded.' }])
  }

  async function undo() {
    setBusy(true)
    try {
      const res = await api.undo(courseId)
      onApplied(res.state)
      setTurns((t) => [...t, { role: 'assistant', content: 'Undid the last applied change.' }])
    } catch (err) {
      setTurns((t) => [
        ...t,
        { role: 'assistant', content: err instanceof Error ? err.message : 'Nothing to undo.' },
      ])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col h-full bg-white border border-stone-200 rounded-2xl overflow-hidden">
      <div className="px-4 py-3 border-b border-stone-200 flex items-center justify-between">
        <h2 className="font-semibold text-stone-900">Assistant</h2>
        <button onClick={undo} disabled={busy} className="text-sm text-stone-500 hover:text-stone-800 disabled:opacity-40">
          ↩ Undo last
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-[12rem]">
        {turns.length === 0 && (
          <div className="text-sm text-stone-500">
            <p className="mb-2">Edit the syllabus in plain English. Try:</p>
            <div className="space-y-1">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  onClick={() => setInput(ex)}
                  className="block text-left w-full px-3 py-1.5 rounded-lg bg-stone-50 hover:bg-stone-100 border border-stone-200 text-stone-700"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}
        {turns.map((t, i) => (
          <div key={i} className={t.role === 'user' ? 'text-right' : 'text-left'}>
            <span
              className={`inline-block px-3 py-2 rounded-2xl text-sm max-w-[90%] ${
                t.role === 'user' ? 'bg-amber-700 text-white' : 'bg-stone-100 text-stone-800'
              }`}
            >
              {t.content}
            </span>
          </div>
        ))}

        {proposal && (
          <div className="border border-amber-300 bg-amber-50 rounded-xl p-3">
            <p className="text-sm font-medium text-stone-800 mb-2">Proposed changes</p>
            <ul className="text-sm text-stone-700 space-y-1 mb-3 list-disc list-inside">
              {proposal.diff.map((d, i) => (
                <li key={i}>{d.summary}</li>
              ))}
              {proposal.diff.length === 0 && <li>No visible changes.</li>}
            </ul>
            <div className="flex gap-2">
              <button onClick={confirm} disabled={busy} className="bg-amber-700 text-white text-sm rounded-lg px-3 py-1.5 hover:bg-amber-800 disabled:opacity-50">
                Confirm
              </button>
              <button onClick={discard} disabled={busy} className="bg-white border border-stone-300 text-stone-700 text-sm rounded-lg px-3 py-1.5 hover:bg-stone-50">
                Discard
              </button>
            </div>
          </div>
        )}
      </div>

      <form onSubmit={send} className="p-3 border-t border-stone-200 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask for a change…"
          className="flex-1 border border-stone-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-600/40"
        />
        <button disabled={busy || !input.trim()} className="bg-amber-700 text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-amber-800 disabled:opacity-50">
          {busy ? '…' : 'Send'}
        </button>
      </form>
    </div>
  )
}
