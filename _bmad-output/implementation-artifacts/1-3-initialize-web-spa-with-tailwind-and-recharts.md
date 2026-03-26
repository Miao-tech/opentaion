# Story 1.3: Initialize Web SPA with Tailwind and Recharts

Status: done

## Story

As a developer building OpenTalon,
I want the web project scaffolded with Vite + React-TS, Tailwind configured, Recharts installed, and a shell App component,
So that the web surface is deployable and ready for authenticated/unauthenticated view implementation.

## Acceptance Criteria

**AC1 — Directory structure is correct:**
Given the web project is initialized
When `web/` is examined
Then it contains ALL of the following:
- A Vite + React-TS project structure (see Final Directory Structure below)
- `tailwind.config.js` configured with `content: ["./src/**/*.{ts,tsx}"]`
- `postcss.config.js` with `tailwindcss` and `autoprefixer` plugins
- `recharts` and `@supabase/supabase-js` in `package.json` dependencies
- `src/App.tsx` with a conditional render stub: `user ? <div>Dashboard</div> : <div>Login</div>`
- `src/index.css` with only Tailwind directives (no default Vite styles)
- `.env.local.example` listing both required env vars

**AC2 — Dev server starts without errors:**
Given `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` are set in `.env.local`
When `npm run dev` is executed from `web/`
Then the dev server starts without errors and the shell renders in a browser with no console errors

**AC3 — Production build succeeds:**
Given `npm run build` is executed from `web/`
When the build completes
Then it exits with code 0 and produces a `dist/` directory

## Tasks / Subtasks

- [x] Task 1: Check existing `web/` directory state before initializing (AC: 1)
  - [x] Run `ls web/` — if `package.json` already exists, read it before proceeding
  - [x] If `web/` is empty or does not have a Vite scaffold: run `npm create vite@latest web -- --template react-ts` from the project root
  - [x] If `web/` already has a Vite scaffold: adjust to match the required structure instead of re-scaffolding

- [x] Task 2: Install dependencies (AC: 1)
  - [x] `npm install` (install scaffold deps)
  - [x] `npm install -D tailwindcss@3 postcss autoprefixer` (Tailwind v3 — explicit version required)
  - [x] `npm install recharts @supabase/supabase-js`
  - [x] Verify all four packages appear in `package.json`

- [x] Task 3: Configure Tailwind CSS v3 (AC: 1, 2)
  - [x] Run `npx tailwindcss init -p` from `web/` to generate `tailwind.config.js` and `postcss.config.js`
  - [x] Update `tailwind.config.js` content array to `["./src/**/*.{ts,tsx}"]` (see Dev Notes)
  - [x] Replace `src/index.css` with only the three Tailwind directives (see Dev Notes)
  - [x] Delete `src/App.css` — Tailwind replaces it completely
  - [x] Remove the `import './App.css'` line from `src/App.tsx` if it exists

- [x] Task 4: Create `src/App.tsx` shell component (AC: 1, 2)
  - [x] Replace the default Vite counter app with the shell stub (see Dev Notes)
  - [x] Shell must: initialize Supabase client, listen to auth state, conditionally render Dashboard/Login divs
  - [x] Do NOT implement actual `<LoginForm>` or `<Dashboard>` components yet — plain `<div>` stubs only

- [x] Task 5: Create environment configuration (AC: 1, 2)
  - [x] Create `.env.local.example` with placeholder values (see Dev Notes)
  - [x] Create `.env.local` with real Supabase values (this file must be in `.gitignore`)
  - [x] Verify `.gitignore` includes `.env.local` (Vite scaffolds this automatically)

- [x] Task 6: Verify AC2 and AC3 (AC: 2, 3)
  - [x] Set `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` in `.env.local`
  - [x] Run `npm run dev` — confirm dev server starts, browser shows "Dashboard" or "Login" text
  - [x] Run `npm run build` — confirm exits 0 and `dist/` is created
  - [x] Run `npm run build && ls dist/` to verify output

## Dev Notes

### Pre-existing `web/` directory — CHECK FIRST

`web/` appears as untracked in git. **Before any scaffold command, check its current state:**

```bash
ls web/
```

- If `package.json` already exists → read it with `cat web/package.json`, then adjust to match requirements instead of re-scaffolding
- If `web/` is empty or has partial content → safe to run the scaffold command
- **Never blindly overwrite** existing work

### Scaffold Command

Run from the **project root** (not from inside `web/`):

```bash
npm create vite@latest web -- --template react-ts
```

This creates `web/` with React 18 + TypeScript. If `web/` already exists and is non-empty, Vite will ask for confirmation — confirm only if you've verified it's safe.

### Package Manager — npm (NOT uv)

This is the web component. Use **npm**, not uv/pip/poetry:
- Install: `npm install`
- Dev deps: `npm install -D <package>`
- Run: `npm run dev`, `npm run build`

The CLI and API use `uv`. The web uses `npm`. Do not mix them.

### Tailwind CSS v3 — CRITICAL: Use Version 3, Not 4

**Install command must explicitly target v3:**
```bash
npm install -D tailwindcss@3 postcss autoprefixer
```

Tailwind v4 (released 2025) has a completely different configuration API — no `tailwind.config.js`, different directive syntax. This project uses **v3** exclusively. If `npm install -D tailwindcss` installs v4, the config below will fail. Always pin to `tailwindcss@3`.

### Required `tailwind.config.js`

```js
// tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

Note: content pattern is `{ts,tsx}` only — no `.js` or `.jsx` since this is a TypeScript project.

### Required `postcss.config.js`

```js
// postcss.config.js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

### Required `src/index.css`

Replace the entire file with only Tailwind directives. Remove ALL default Vite CSS:

```css
/* src/index.css */
@tailwind base;
@tailwind components;
@tailwind utilities;
```

`main.tsx` imports this file — do not delete it. Just replace its contents.

### Required `src/App.tsx`

This is the shell component. It sets up Supabase auth state and conditionally renders stubs. The actual `<LoginForm>`, `<Sidebar>`, and dashboard components come in Stories 2.3, 2.4, 2.5:

```tsx
// src/App.tsx
import { useEffect, useState } from 'react'
import { createClient } from '@supabase/supabase-js'
import type { User } from '@supabase/supabase-js'

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL as string,
  import.meta.env.VITE_SUPABASE_ANON_KEY as string
)

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

  return user ? <div>Dashboard</div> : <div>Login</div>
}

export default App
```

**Why this exact shape?**
- `supabase` client is module-level — one instance for the lifetime of the app (Story 2.3 will extend this pattern, not replace it)
- `user` state is `User | null` — typed from Supabase SDK, not a raw string
- `getSession()` on mount handles browser refresh (restores existing session)
- `onAuthStateChange()` handles magic link callback and sign-out (Stories 2.3, 2.6 depend on this)
- Cleanup: `subscription.unsubscribe()` prevents memory leaks
- The return `user ? <div>Dashboard</div> : <div>Login</div>` is the exact stub shape specified in the epics acceptance criteria

### Required `.env.local.example`

Create this file in `web/` — it documents what's needed but contains no real values:

```
# web/.env.local.example
# Copy to .env.local and fill in your Supabase project values
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key-here
```

For local development, create `.env.local` (already gitignored by Vite):
```
# web/.env.local  — DO NOT COMMIT
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key-here
```

If you don't have a Supabase project yet, use placeholder values for AC2/AC3 verification — the app will still render (auth will silently fail but the shell renders). Story 1.4 is where the real Supabase project is configured.

### Vite TypeScript Env Var Access

Vite exposes env vars via `import.meta.env.VITE_*`. In TypeScript, these are typed as `string | undefined` by default. The `as string` cast in App.tsx is intentional — we know these are required.

Do NOT use `process.env` — that is Node.js. In Vite, always use `import.meta.env`.

### Cleanup — Remove Vite Boilerplate

The `react-ts` template generates a counter example app. After scaffolding, remove:
- `src/App.css` — delete this file entirely
- `public/vite.svg` — optional, can leave
- `src/assets/react.svg` — optional, can leave
- The `import './App.css'` line in App.tsx (if it exists)
- Replace `src/index.css` contents with Tailwind directives

Do NOT delete:
- `src/main.tsx` — entry point, keep as-is
- `index.html` — Vite's HTML shell, keep as-is
- `vite.config.ts` — build config, keep as generated
- `tsconfig.json`, `tsconfig.node.json` — TypeScript config, keep as generated

### Design Token Preview (Used in Later Stories)

The design system will use exactly these Tailwind classes. This story creates the foundation — future stories apply them:

| Purpose | Token |
|---|---|
| Page background | `bg-gray-50` |
| Card/surface | `bg-white` |
| Borders | `border-gray-200` |
| Primary text | `text-gray-900` |
| Secondary text | `text-gray-500` |
| Accent (buttons, nav active) | `bg-blue-600` / `text-blue-600` |
| Accent subtle (nav active bg) | `bg-blue-50` |
| Destructive (revoke) | `text-red-600` |

These come from `epics.md UX-DR9` and `ux-design-specification.md`. No shadcn/ui, no component library — raw Tailwind utilities only.

### No Routing Library

This project intentionally has **no React Router or similar**. Navigation between Dashboard and API Keys views is handled via `activeView` state in `App.tsx`. This is established in Story 1.3 (the stub only has `user ? Dashboard : Login`) and extended in Story 2.4 (which adds the sidebar with `activeView` state).

Do not add `react-router-dom`, `tanstack/router`, or any routing package.

### Final Directory Structure

After this story is complete, `web/` must look like this:

```
web/
├── package.json           # includes recharts, @supabase/supabase-js, tailwindcss@3
├── package-lock.json
├── vite.config.ts
├── tsconfig.json
├── tsconfig.node.json
├── tailwind.config.js     # content: ["./src/**/*.{ts,tsx}"]
├── postcss.config.js      # tailwindcss + autoprefixer
├── index.html
├── .env.local             # real values — gitignored
├── .env.local.example     # placeholder values — committed
├── .gitignore             # includes .env.local (Vite adds this)
├── public/
│   └── vite.svg           # can leave as-is
└── src/
    ├── main.tsx           # unchanged from scaffold
    ├── index.css          # Tailwind directives only (@tailwind base/components/utilities)
    ├── App.tsx            # shell with supabase auth state + conditional render
    ├── vite-env.d.ts      # unchanged from scaffold
    └── assets/
        └── react.svg      # can leave as-is
```

### Architecture Cross-References

From `architecture.md`:
- Web frontend: Vite 5.x + React 18 + TypeScript, Tailwind CSS 3.x, Recharts, no routing library [Source: architecture.md#Web Frontend]
- Supabase client: `createClient(VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY)` at module level [Source: architecture.md#Authentication & Security]
- Two views: conditional render on Supabase `session` state — no URL routing [Source: architecture.md#Core Architectural Decisions]
- `activeView` state lives in `App.tsx` (added in Story 2.4, stub only in this story) [Source: architecture.md#Web Frontend]
- Starter template: `npm create vite@latest web -- --template react-ts` + Tailwind + Recharts [Source: epics.md#Additional Requirements]

From `epics.md`:
- No shadcn/ui — setup requires interactive CLI, tsconfig path alias changes, and per-component installs; Tailwind utilities are sufficient [Source: CLAUDE.md#4]
- `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` required in `.env.local` [Source: epics.md#Story 1.3]
- Recharts used for bar chart in Story 4.2 — installed now to avoid churn later [Source: epics.md#Story 4.2]

From `ux-design-specification.md`:
- `<App>` is the root component with `activeView` and `session` state [Source: ux-design-specification.md#Component Strategy]
- Phase 1 (this story): auth shell scaffold only [Source: ux-design-specification.md#Implementation Roadmap]
- No state management library — plain React `useState`/`useEffect` [Source: ux-design-specification.md#Component Strategy]

### Previous Story Learnings

From Story 1.1 (CLI):
- **Check existing directory before initializing** — `web/` is untracked in git, may already have content
- Package manager discipline: CLI uses `uv`, web uses `npm` — don't mix
- Establish conventions early that all subsequent stories inherit

From Story 1.2 (API):
- **TDD was specified for API** — web scaffold stories don't have the same test requirement, but build verification (`npm run build`) is the equivalent gate
- Supabase SDK installed early (Story 1.2 added it even though unused) — same philosophy here: Recharts is installed now even though the chart component is Story 4.2
- Railway `postgresql://` → `postgresql+asyncpg://` URL fix: analogous here is Vite's `import.meta.env` vs Node's `process.env` — easy to get wrong, explicit in Dev Notes

### What This Story Does NOT Include

Do NOT implement any of the following — they belong to later stories:

- `<LoginForm>` component with magic link UI (Story 2.3)
- `<Sidebar>` component with navigation (Story 2.4)
- `<ApiKeyList>`, `<NewKeyBanner>`, `<GenerateKeyButton>` components (Story 2.5)
- `<UsageChart>` with Recharts (Story 4.2)
- `<ModelTable>` component (Story 4.2)
- `activeView` state with Dashboard/API Keys toggle (Story 2.4 — stub returns `<div>Dashboard</div>` only)
- Real Supabase auth flow with `signInWithOtp` (Story 2.3 — App.tsx only reads session)
- Any API calls to the FastAPI backend
- Deployment to Vercel (Story 1.6)
- TypeScript path aliases (`@/` imports) — not needed, adds tsconfig complexity for no benefit

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

_none_

### Completion Notes List

- `web/` already had a full Vite + React-TS scaffold with recharts v2.12.7 and Tailwind v3.4.4 — no re-scaffolding needed
- `@supabase/supabase-js` was missing — installed (v2.100.0 added to dependencies)
- `tailwind.config.ts` existed (TS format, included `./index.html` in content) — replaced with spec-conformant `tailwind.config.js` (ESM, content `["./src/**/*.{ts,tsx}"]`)
- `postcss.config.js` used CJS `module.exports` — updated to ESM `export default` to match spec and avoid Node warning
- `src/App.tsx` had a working app with Login/Dashboard components and mock data — replaced with the Supabase auth stub as specified
- `src/vite-env.d.ts` was missing from the scaffold — created with `/// <reference types="vite/client" />` to resolve `import.meta.env` TypeScript error
- `"type": "module"` added to `package.json` to silence MODULE_TYPELESS_PACKAGE_JSON Node warning
- `.env.local` created with placeholder values (placeholder Supabase URL/key — story notes state this is sufficient for build verification)
- `npm run build` exits 0, produces `dist/` with 337 kB JS bundle — AC3 satisfied

### File List

- `web/tailwind.config.js` — NEW (replaced tailwind.config.ts)
- `web/postcss.config.js` — MODIFIED (CJS → ESM format)
- `web/package.json` — MODIFIED (added `@supabase/supabase-js`, `"type": "module"`)
- `web/package-lock.json` — MODIFIED (lock file updated)
- `web/src/App.tsx` — MODIFIED (replaced with Supabase auth stub)
- `web/src/vite-env.d.ts` — NEW (Vite env type reference)
- `web/.env.local.example` — NEW
- `web/.env.local` — NEW (placeholder values, gitignored)
