import { useState, type FormEvent } from 'react'
import { api, ApiError, setToken } from '../api'

export default function Login({ onLogin }: { onLogin: () => void }) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const { token } = await api.login(password)
      setToken(token)
      onLogin()
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError('Incorrect password.')
      } else {
        setError(
          err instanceof Error
            ? `Could not reach the server (${err.message}). Is the backend running and the Vite proxy pointed at it?`
            : 'Sign-in failed.',
        )
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen grid place-items-center bg-stone-100 px-4">
      <form
        onSubmit={submit}
        className="w-full max-w-sm bg-white rounded-2xl shadow-sm border border-stone-200 p-7"
      >
        <h1 className="text-xl font-semibold text-stone-900">Instructor sign-in</h1>
        <p className="text-sm text-stone-500 mt-1 mb-5">Interactive Syllabus</p>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Admin password"
          autoFocus
          className="w-full border border-stone-300 rounded-lg px-3 py-2 mb-3 focus:outline-none focus:ring-2 focus:ring-amber-600/40"
        />
        {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
        <button
          disabled={busy}
          className="w-full bg-amber-700 text-white rounded-lg py-2 font-medium hover:bg-amber-800 disabled:opacity-50"
        >
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}
