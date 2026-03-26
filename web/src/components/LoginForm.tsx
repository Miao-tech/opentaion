// src/components/LoginForm.tsx
import { useState } from 'react'
import { supabase } from '../lib/supabase'

type FormState = 'idle' | 'sending' | 'sent' | 'error'

export function LoginForm() {
  const [email, setEmail] = useState('')
  const [formState, setFormState] = useState<FormState>('idle')
  const [errorMessage, setErrorMessage] = useState('')

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const trimmedEmail = email.trim()
    if (!trimmedEmail) {
      setErrorMessage('Please enter your email address.')
      setFormState('error')
      return
    }
    setFormState('sending')
    setErrorMessage('')

    const { error } = await supabase.auth.signInWithOtp({ email: trimmedEmail })

    if (error) {
      setErrorMessage(error.message || 'Something went wrong. Please try again.')
      setFormState('error')
    } else {
      setFormState('sent')
    }
  }

  // ── Post-send confirmation state ─────────────────────────────────────────
  if (formState === 'sent') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm w-full max-w-sm p-8">
          <h1 className="text-xl font-semibold text-gray-900 mb-6">OpenTalon</h1>
          <p className="text-sm text-gray-500">
            ✉ Check your email for a sign-in link. The link expires in 10 minutes.
          </p>
        </div>
      </div>
    )
  }

  // ── Form state (idle | sending | error) ──────────────────────────────────
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm w-full max-w-sm p-8">
        <h1 className="text-xl font-semibold text-gray-900 mb-6">OpenTalon</h1>

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <div className="space-y-1">
            <label
              htmlFor="email"
              className="block text-sm text-gray-900"
            >
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              disabled={formState === 'sending'}
              className="w-full border border-gray-200 rounded px-3 py-2 text-sm text-gray-900 placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
              placeholder="you@example.com"
            />
          </div>

          {formState === 'error' && (
            <p role="alert" className="text-red-600 text-sm">
              {errorMessage}
            </p>
          )}

          <button
            type="submit"
            disabled={formState === 'sending'}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-2 px-4 rounded transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {formState === 'sending' ? 'Sending...' : 'Send magic link'}
          </button>
        </form>
      </div>
    </div>
  )
}
