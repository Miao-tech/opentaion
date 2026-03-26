# Story 2.3: Web Auth Shell — Login Page with Magic Link

Status: done

## Story

As a developer building OpenTalon,
I want the web login page implemented with a Supabase magic link flow,
So that a new developer can authenticate and reach the dashboard.

## Acceptance Criteria

**AC1 — Unauthenticated view renders `<LoginForm>` with correct layout:**
Given the web app is loaded and the user is unauthenticated
When the page renders
Then the `<LoginForm>` component displays: a centered card with the "OpenTalon" heading, an email input with `<label>` associated via `htmlFor`, and a "Send magic link" primary button

**AC2 — Successful `signInWithOtp` transitions to post-send confirmation:**
Given the user enters a valid email and clicks "Send magic link"
When the Supabase `signInWithOtp` call succeeds
Then the form is replaced with: "✉ Check your email for a sign-in link. The link expires in 10 minutes."

**AC3 — Magic link click authenticates and renders authenticated view:**
Given the user clicks a valid magic link in their email
When the Supabase session is established
Then `supabase.auth.onAuthStateChange()` fires, `user` state is set, and the authenticated view renders ("Dashboard" stub from Story 1.3)

**AC4 — `signInWithOtp` failure shows inline error:**
Given the `signInWithOtp` call fails
When the error occurs
Then an error message is shown in `text-red-600 text-sm` with `role="alert"` below the input

**AC5 — Browser refresh restores existing session:**
Given an authenticated session already exists
When the app loads (browser refresh)
Then the user is taken directly to the authenticated view without re-entering email

**AC6 — All interactive elements have correct focus rings:**
Given all interactive elements (input, button)
When navigated via keyboard
Then all elements have: `focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2`

**AC7 — Build succeeds:**
Given `npm run build` is executed from `web/`
When TypeScript compilation and Vite bundling complete
Then it exits with code 0 (no TypeScript errors)

## Tasks / Subtasks

- [x] Task 1: Extract Supabase client to shared module (AC: 3, 5)
  - [x] Create `src/lib/supabase.ts` with the module-level Supabase client (see Dev Notes)
  - [x] Update `src/App.tsx` to `import { supabase } from './lib/supabase'` instead of creating inline

- [x] Task 2: Create `<LoginForm>` component (AC: 1, 2, 4, 6)
  - [x] Create `src/components/LoginForm.tsx` (see Dev Notes for exact implementation)
  - [x] Two render paths: form state and post-send confirmation state
  - [x] Apply all design tokens from UX spec: colors, typography, focus rings
  - [x] Error state: `role="alert"`, `text-red-600 text-sm`, co-located below the input

- [x] Task 3: Update `App.tsx` to use `<LoginForm>` (AC: 1, 3, 5)
  - [x] Replace `<div>Login</div>` with `<LoginForm />`
  - [x] Import `LoginForm` from `./components/LoginForm`
  - [x] Auth state management (`getSession` + `onAuthStateChange`) stays in `App.tsx` — not moved

- [x] Task 4: Verify locally (AC: 1–6)
  - [ ] `npm run dev` from `web/` — confirm dev server starts without errors (manual)
  - [ ] Open browser → confirm "Login" card renders centered on gray background (manual)
  - [ ] Enter email → click "Send magic link" → confirm post-send text appears (manual)
  - [ ] Check browser console — no TypeScript or React errors (manual)
  - [x] `npm run build` — confirm exits 0

## Dev Notes

### Prerequisite: Story 1.3 Must Be Complete

Story 1.3 established `App.tsx` with the Supabase client inline and the `user ? <div>Dashboard</div> : <div>Login</div>` stub. This story modifies that file — the Supabase client moves to `src/lib/supabase.ts` and `<div>Login</div>` becomes `<LoginForm />`.

### Architecture Decision: Extract Supabase Client to `src/lib/supabase.ts`

Story 1.3 created the Supabase client inline in `App.tsx`. Starting this story, `<LoginForm>` also needs the client (to call `signInWithOtp`). Rather than passing it as a prop (prop drilling) or creating a second instance, extract it to a shared module:

```typescript
// src/lib/supabase.ts
import { createClient } from '@supabase/supabase-js'

export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL as string,
  import.meta.env.VITE_SUPABASE_ANON_KEY as string
)
```

This is a module-level singleton — imported everywhere the Supabase client is needed. All future components that need Supabase (`<GenerateKeyButton>`, `<ApiKeyList>`, etc.) will import from this module.

**Update `src/App.tsx`** to import from the new module instead of creating inline:

```tsx
// src/App.tsx
import { useEffect, useState } from 'react'
import type { User } from '@supabase/supabase-js'
import { supabase } from './lib/supabase'
import { LoginForm } from './components/LoginForm'

function App() {
  const [user, setUser] = useState<User | null>(null)

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null)
    })

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null)
    })

    return () => subscription.unsubscribe()
  }, [])

  return user ? <div>Dashboard</div> : <LoginForm />
}

export default App
```

The auth state logic (`getSession` + `onAuthStateChange`) stays in `App.tsx` — `LoginForm` only calls `signInWithOtp`, it does not manage session state. Sessions are managed at the App level only.

### `<LoginForm>` Component — Full Implementation

Create `src/components/LoginForm.tsx`:

```tsx
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
    setFormState('sending')
    setErrorMessage('')

    const { error } = await supabase.auth.signInWithOtp({ email })

    if (error) {
      setErrorMessage(error.message)
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
              className="w-full border border-gray-200 rounded px-3 py-2 text-sm text-gray-900 placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
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
```

### Design Token Compliance — Every Class is Required

Each class maps to an explicit UX requirement:

| Element | Classes | Requirement |
|---|---|---|
| Page wrapper | `min-h-screen bg-gray-50 flex items-center justify-center p-4` | UX-DR9: page background `bg-gray-50` |
| Card | `bg-white rounded-lg border border-gray-200 shadow-sm w-full max-w-sm p-8` | UX-DR9: surface `bg-white`, border `border-gray-200` |
| Heading | `text-xl font-semibold text-gray-900` | UX-DR9: page heading scale |
| Label | `block text-sm text-gray-900` | UX-DR9: body text |
| Input | `border border-gray-200 ... text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2` | UX-DR10: focus rings; UX-DR9: border/text |
| Error | `text-red-600 text-sm` + `role="alert"` | UX-DR2: error state; UX-DR9: destructive color |
| Primary button | `bg-blue-600 hover:bg-blue-700 text-white ... transition-colors duration-150` | UX-DR12: primary button; UX-DR10: focus rings |
| Disabled button | `disabled:opacity-50 disabled:cursor-not-allowed` | UX-DR12: disabled state |

**Do not substitute tokens.** `bg-blue-500` is not the same as `bg-blue-600`. `text-gray-600` is not the same as `text-gray-500`. The UX spec defines exact shades.

### Supabase Magic Link Flow — What Actually Happens

Understanding this prevents debugging confusion:

1. User enters email → `signInWithOtp({ email })` → Supabase sends email → returns `{ error: null }`
2. Form transitions to post-send state (this story's AC2)
3. User opens email → clicks link → browser opens `https://your-app.vercel.app/#access_token=...&type=magiclink`
4. Supabase JS SDK intercepts the URL fragment automatically
5. `onAuthStateChange` in `App.tsx` fires with `event = "SIGNED_IN"` and a valid session
6. `user` state updates → `App` re-renders → `user ? <div>Dashboard</div> : <LoginForm />` shows dashboard (AC3)

**The magic link redirect URL must match Supabase's allowed redirects.** In Supabase Dashboard → Authentication → URL Configuration → Site URL, add your Vercel URL. For local dev, add `http://localhost:5173`. Without this, the magic link redirects to a wrong URL and the session won't be established.

### No Test File for This Story

Unlike the API stories, the web has no automated test suite configured at this stage. Verification is manual:
1. `npm run build` — TypeScript compilation is the automated gate (AC7)
2. Manual browser testing for auth flow (AC1–AC6)

If a test framework (Vitest + React Testing Library) is added in a future story, `<LoginForm>` tests would cover: render in idle state, render in sent state, error message display, and form submission behavior.

### Directory Structure After This Story

Two new files, two modified files:

```
web/src/
├── App.tsx              # MODIFIED — imports supabase from lib, uses <LoginForm>
├── lib/
│   └── supabase.ts      # NEW — module-level Supabase client singleton
└── components/
    └── LoginForm.tsx    # NEW — email form + post-send confirmation
```

The `src/components/` and `src/lib/` directories are created by adding these files.

### What `noValidate` Does

The `<form noValidate>` attribute disables browser-native HTML5 validation (the ugly tooltip popups). This gives us control over when and how validation messages appear. In this case, the button is `type="submit"` and the input has `required` — but `noValidate` means the browser won't show its default validation UI. Instead, if the user submits with an empty email, `signInWithOtp` will return an error and the custom `role="alert"` error element displays it.

### Architecture Cross-References

From `ux-design-specification.md`:
- UX-DR2: `<LoginForm>` — two states, form/post-send, `role="alert"` error [Source: ux-design-specification.md#Component Strategy]
- UX-DR9: 6-color semantic palette — exact Tailwind classes documented above [Source: ux-design-specification.md#Design System Foundation]
- UX-DR10: `focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2` on ALL interactive elements [Source: ux-design-specification.md#UX Consistency Patterns]
- UX-DR11: `<label htmlFor>` + `id` association on form inputs [Source: ux-design-specification.md#UX Consistency Patterns]
- UX-DR12: Primary button `bg-blue-600 hover:bg-blue-700 text-white`, disabled `opacity-50 cursor-not-allowed` [Source: ux-design-specification.md#UX Consistency Patterns]

From `epics.md`:
- FR1: "Developer can authenticate the CLI by receiving a magic link at their email address" [Source: epics.md#FR1]
- FR5: "Developer can authenticate the web dashboard by receiving a magic link at their email address" [Source: epics.md#FR5]
- NFR8: "User email address is the only PII stored in the system; no passwords are stored anywhere" — magic link auth enforces this [Source: epics.md#NFR8]

From `architecture.md`:
- Supabase client: `createClient(VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY)` at module level — extracted to `src/lib/supabase.ts` [Source: architecture.md#Authentication & Security]
- No router library — two views via conditional render on auth state [Source: architecture.md#Core Architectural Decisions]

### What This Story Does NOT Include

Do NOT implement any of the following:

- `<Sidebar>` component (Story 2.4)
- The authenticated dashboard view beyond the existing `<div>Dashboard</div>` stub (Stories 2.4, 2.5, 4.2)
- Sign-out button (Story 2.4 adds it to the sidebar)
- `<ApiKeyList>`, `<NewKeyBanner>`, `<GenerateKeyButton>` (Story 2.5)
- Any `activeView` state management (Story 2.4)
- `VITE_API_BASE_URL` usage — the LoginForm only calls Supabase, not the FastAPI API

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

_none_

### Completion Notes List

- Created `src/lib/supabase.ts` — module-level Supabase client singleton extracted from App.tsx
- Created `src/components/LoginForm.tsx` — full implementation: idle/sending/sent/error states, all UX design tokens applied exactly (bg-gray-50, bg-white, border-gray-200, text-gray-900, bg-blue-600, text-red-600, focus:ring-blue-500)
- Updated `App.tsx` — imports supabase from lib, uses `<LoginForm />` for unauthenticated view, auth state management stays in App.tsx
- `npm run build` exits 0 — TypeScript strict-mode compiles cleanly, 73 modules transformed
- AC1–AC6 require manual browser verification; AC7 (build) automated and confirmed

### File List

- `web/src/lib/supabase.ts` — NEW: module-level Supabase client singleton
- `web/src/components/LoginForm.tsx` — NEW: email form + post-send confirmation component
- `web/src/App.tsx` — MODIFIED: imports supabase from lib, uses LoginForm

## Change Log

- 2026-03-25: Story 2.3 implemented — LoginForm component with magic link flow; Supabase client extracted to shared module; npm run build exits 0
