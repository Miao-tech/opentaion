# Story 2.4: Web Authenticated Shell — Sidebar Navigation

Status: ready-for-dev

## Story

As a developer building OpenTalon,
I want the authenticated app shell implemented with the `<Sidebar>` and conditional view rendering,
So that an authenticated user can navigate between the Dashboard and API Keys views.

## Acceptance Criteria

**AC1 — Two-panel layout renders when authenticated:**
Given the user is authenticated
When the app renders
Then a `<aside>` with `w-[220px]` fixed sidebar and a `<main className="flex-1 p-6">` content area are displayed

**AC2 — Sidebar contains correct navigation structure:**
Given the authenticated shell is visible
When the sidebar is inspected
Then it contains: the "OpenTalon" label, a `<nav aria-label="Main navigation">` with "Dashboard" and "API Keys" `<button>` elements, and a "Sign out" button

**AC3 — Dashboard view is the default active view:**
Given the user just authenticated
When the app first renders the authenticated shell
Then the "Dashboard" nav item has `bg-blue-50 text-blue-600 rounded-md` active styling with `aria-current="page"` and the main content area shows the dashboard stub

**AC4 — Clicking "API Keys" switches view:**
Given the user clicks "API Keys" in the sidebar
When `activeView` state changes to `"keys"`
Then the "API Keys" nav item has active styling with `aria-current="page"` and the main content area shows the API keys stub

**AC5 — Sign-out clears session and returns to login:**
Given the user clicks the "Sign out" button
When `supabase.auth.signOut()` is called
Then the session is cleared, `onAuthStateChange` fires in `App.tsx`, `user` becomes null, and `<LoginForm>` renders

**AC6 — All interactive elements have correct focus rings:**
Given all sidebar buttons (Dashboard, API Keys, Sign out)
When navigated via keyboard
Then all have: `focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2`

**AC7 — Build succeeds:**
Given `npm run build` is executed from `web/`
Then it exits with code 0 (no TypeScript errors)

## Tasks / Subtasks

- [ ] Task 1: Create `<Sidebar>` component (AC: 1, 2, 3, 4, 5, 6)
  - [ ] Create `src/components/Sidebar.tsx` (see Dev Notes for full implementation)
  - [ ] Props: `activeView`, `onViewChange`, `onSignOut`
  - [ ] Apply all UX-DR1 requirements: fixed width, `<aside>`, `<nav aria-label>`, `aria-current`, `<button>` elements

- [ ] Task 2: Update `App.tsx` to render the full authenticated shell (AC: 1, 3, 4, 5)
  - [ ] Add `activeView` state: `useState<'dashboard' | 'keys'>('dashboard')`
  - [ ] Replace `user ? <div>Dashboard</div> : <LoginForm />` with the two-panel layout
  - [ ] Pass `onSignOut={() => supabase.auth.signOut()}` — sign-out triggers `onAuthStateChange` automatically
  - [ ] Content area: `activeView === 'dashboard' ? <div>Dashboard</div> : <div>API Keys</div>`

- [ ] Task 3: Verify locally (AC: 1–7)
  - [ ] `npm run dev` → authenticate → confirm two-panel layout appears
  - [ ] Click "API Keys" → confirm view stub switches
  - [ ] Click "Sign out" → confirm login form reappears
  - [ ] `npm run build` → confirm exits 0

## Dev Notes

### Prerequisite: Story 2.3 Must Be Complete

- `src/lib/supabase.ts` must exist (created in Story 2.3) — `<Sidebar>` imports `supabase` for sign-out
- `src/components/LoginForm.tsx` must exist — `App.tsx` still renders it when unauthenticated
- `App.tsx` must already import `supabase` from `./lib/supabase` (Story 2.3 moved it there)

### `<Sidebar>` Component — Full Implementation

Create `src/components/Sidebar.tsx`:

```tsx
// src/components/Sidebar.tsx
import { supabase } from '../lib/supabase'

type View = 'dashboard' | 'keys'

interface SidebarProps {
  activeView: View
  onViewChange: (view: View) => void
}

const navItems: { view: View; label: string }[] = [
  { view: 'dashboard', label: 'Dashboard' },
  { view: 'keys', label: 'API Keys' },
]

export function Sidebar({ activeView, onViewChange }: SidebarProps) {
  return (
    <aside className="w-[220px] bg-white border-r border-gray-200 flex flex-col h-screen flex-shrink-0">
      {/* Logo / product name */}
      <div className="px-6 py-5 border-b border-gray-200">
        <span className="text-sm font-medium text-gray-900">OpenTalon</span>
      </div>

      {/* Navigation */}
      <nav aria-label="Main navigation" className="flex-1 px-3 py-4 space-y-1">
        {navItems.map(({ view, label }) => (
          <button
            key={view}
            onClick={() => onViewChange(view)}
            aria-current={activeView === view ? 'page' : undefined}
            className={[
              'w-full text-left px-3 py-2 rounded-md text-sm transition-colors duration-150',
              'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2',
              activeView === view
                ? 'bg-blue-50 text-blue-600'
                : 'text-gray-900 hover:bg-gray-50',
            ].join(' ')}
          >
            {label}
          </button>
        ))}
      </nav>

      {/* Sign out */}
      <div className="px-3 py-4 border-t border-gray-200">
        <button
          onClick={() => supabase.auth.signOut()}
          className="w-full text-left px-3 py-2 rounded-md text-sm text-gray-500 hover:bg-gray-50 transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
        >
          Sign out
        </button>
      </div>
    </aside>
  )
}
```

**Why does `<Sidebar>` import `supabase` directly for sign-out?**
The `onSignOut` callback would need to live in `App.tsx` and be passed as a prop — but `supabase.auth.signOut()` is a one-liner with no return value needed. Importing `supabase` directly from the module keeps `App.tsx` cleaner and avoids an extra prop. The `onAuthStateChange` listener in `App.tsx` handles the state update automatically when signOut fires.

**Why no `onSignOut` prop?**
`signOut()` has no meaningful return value to handle. The `onAuthStateChange` listener in `App.tsx` already responds to the `SIGNED_OUT` event — no callback needed. Passing it as a prop would be a leaky abstraction.

**`aria-current={activeView === view ? 'page' : undefined}`**
`aria-current="page"` is the ARIA attribute for the currently active navigation item. `undefined` omits the attribute entirely when not active — do not use `aria-current="false"` (some screen readers announce "false" explicitly).

**`flex-shrink-0` on `<aside>`**
Prevents the sidebar from shrinking when the content area is wide. Without it, a flex child might compress the sidebar below 220px on smaller viewports.

### Updated `App.tsx` — Full File

```tsx
// src/App.tsx
import { useEffect, useState } from 'react'
import type { User } from '@supabase/supabase-js'
import { supabase } from './lib/supabase'
import { LoginForm } from './components/LoginForm'
import { Sidebar } from './components/Sidebar'

type View = 'dashboard' | 'keys'

function App() {
  const [user, setUser] = useState<User | null>(null)
  const [activeView, setActiveView] = useState<View>('dashboard')

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

  if (!user) {
    return <LoginForm />
  }

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar activeView={activeView} onViewChange={setActiveView} />
      <main className="flex-1 overflow-auto p-6">
        {activeView === 'dashboard' ? (
          <div>Dashboard</div>
        ) : (
          <div>API Keys</div>
        )}
      </main>
    </div>
  )
}

export default App
```

**`overflow-auto` on `<main>`**
Allows the content area to scroll when content exceeds the viewport height. Without it, the fixed-height `h-screen` container clips long content.

**`if (!user) return <LoginForm />`**
Cleaner early-return pattern than the ternary. The `activeView` state only matters when the user is authenticated — this structure makes that obvious. Same runtime behavior as the ternary from Story 1.3.

### Sign-Out Flow — How It Works Without a Callback

1. User clicks "Sign out" → `supabase.auth.signOut()` called
2. Supabase clears the session from localStorage
3. `onAuthStateChange` in `App.tsx` fires with `event = "SIGNED_OUT"`, `session = null`
4. `setUser(null)` is called
5. `if (!user) return <LoginForm />` — app re-renders the login form

No explicit callback or state management needed. The `onAuthStateChange` listener established in Story 1.3 handles everything.

### Design Tokens — Sidebar Specific

| Element | Classes | Requirement |
|---|---|---|
| `<aside>` | `w-[220px] bg-white border-r border-gray-200` | UX-DR1: fixed 220px, surface color, border |
| Active nav item | `bg-blue-50 text-blue-600 rounded-md` | UX-DR1: exact active state specification |
| Inactive nav item | `text-gray-900 hover:bg-gray-50` | UX-DR9: primary text, subtle hover |
| Sign out | `text-gray-500` | UX-DR9: secondary text for de-emphasized action |
| All buttons | `focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2` | UX-DR10: mandatory focus rings |
| Transitions | `transition-colors duration-150` | UX-DR12: button hover transitions |

**`w-[220px]` uses Tailwind's arbitrary value syntax** — there is no standard `w-55` or similar that equals exactly 220px. The square brackets are required.

### No Test File for This Story

Same pattern as Story 2.3 — manual browser verification + `npm run build` TypeScript compilation gate. No automated component test suite yet.

### Architecture Cross-References

From `ux-design-specification.md`:
- UX-DR1: `<Sidebar>` — fixed 220px, `<aside>` landmark, `<nav aria-label="Main navigation">`, all items `<button>`, active state `bg-blue-50 text-blue-600 rounded-md`, `aria-current="page"` [Source: ux-design-specification.md#Component Strategy]
- Component tree: `<App>` holds `activeView` and `session` state — both live at the top level [Source: ux-design-specification.md#Component Strategy]
- Navigation is state-based, not URL-based — no router library [Source: ux-design-specification.md#UX Consistency Patterns]
- Sign-out action lives in sidebar — user initiates it without leaving the current view [Source: ux-design-specification.md#Experience Flows]

From `architecture.md`:
- No router library — `activeView` state in `App.tsx`, two views via conditional rendering [Source: architecture.md#Core Architectural Decisions]

From `epics.md`:
- FR23: "Developer can access API key management from the authenticated dashboard" — this story creates the navigation to reach it [Source: epics.md#FR23]

### What This Story Does NOT Include

- `<UsageChart>` or `<ModelTable>` components — those are Story 4.2
- `<ApiKeyList>`, `<NewKeyBanner>`, `<GenerateKeyButton>` — Story 2.5
- The `<main>` content area beyond the plain text stubs — Stories 2.5 and 4.2 replace them
- User profile or settings in the sidebar — not in V1 scope
- Any API calls from the dashboard — the stubs are pure static text

### Final Modified/Created Files

```
web/src/
├── App.tsx                      # MODIFIED — activeView state + two-panel layout
└── components/
    ├── LoginForm.tsx             # unchanged (Story 2.3)
    └── Sidebar.tsx               # NEW — sidebar nav + sign-out
```

## Dev Agent Record

### Agent Model Used

_to be filled by dev agent_

### Debug Log References

_none_

### Completion Notes List

_to be filled by dev agent_

### File List

_to be filled by dev agent_
