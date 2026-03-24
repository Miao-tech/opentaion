# Story 2.5: Web API Keys View — Generate, List, and Revoke

Status: ready-for-dev

## Story

As a developer building OpenTalon,
I want the API Keys view implemented with key generation, the one-time display banner, the key list, and revoke actions,
So that a developer can generate a key to paste into `opentaion login` and manage their active keys.

## Acceptance Criteria

**AC1 — API Keys view renders with generate button and key list:**
Given the user navigates to the API Keys view
When the view renders
Then a "Generate new key" primary button is displayed and existing active keys are shown as a table with truncated preview (`font-mono text-xs text-gray-600`) and "Revoke" destructive text buttons

**AC2 — Empty state shows correct message:**
Given no keys exist
When the key list renders
Then the message "No API keys yet. Generate one to connect your CLI." is shown

**AC3 — Key generation shows the one-time banner:**
Given the user clicks "Generate new key"
When `POST /api/keys` succeeds
Then `<NewKeyBanner>` renders with `role="alert"`, displaying the full plaintext key with "Copy this key now — it won't be shown again." instruction and a copy button

**AC4 — Copy button works with 2-second feedback:**
Given the user clicks the copy button in `<NewKeyBanner>`
When `navigator.clipboard.writeText()` succeeds
Then the button shows "Copied ✓" for 2 seconds then reverts to "Copy"

**AC5 — Revoke removes key from list:**
Given the user clicks "Revoke" on an active key
When `DELETE /api/keys/{key_id}` succeeds
Then the key is removed from the list immediately with no confirmation modal

**AC6 — In-flight revoke shows loading state:**
Given a revoke is in-flight
When the DELETE request is pending
Then the "Revoke" button for that row shows "Revoking..." and is disabled

**AC7 — `VITE_API_BASE_URL` is required:**
Given the env var is set to the Railway API URL
When API calls are made
Then they target the correct backend

**AC8 — Build succeeds:**
Given `npm run build` from `web/`
Then TypeScript compilation exits 0

## Tasks / Subtasks

- [ ] Task 1: Add `VITE_API_BASE_URL` environment variable (AC: 7)
  - [ ] Add to `web/.env.local`: `VITE_API_BASE_URL=https://your-api.up.railway.app`
  - [ ] Add to `web/.env.local.example`
  - [ ] Add to Vercel environment variables after this story is deployed

- [ ] Task 2: Create API client module `src/lib/api.ts` (AC: 1, 3, 5)
  - [ ] Define TypeScript types for API responses (see Dev Notes)
  - [ ] Implement `generateKey()`, `listKeys()`, `revokeKey(id)` using `fetch` + Supabase JWT
  - [ ] Implement `getAuthHeaders()` helper to retrieve the Supabase access token

- [ ] Task 3: Create `<GenerateKeyButton>` component (AC: 3, UX-DR7)
  - [ ] Loading state: "Generating..." + `opacity-75 cursor-not-allowed`
  - [ ] Disabled during in-flight request
  - [ ] `onKeyGenerated` callback prop with the API response

- [ ] Task 4: Create `<NewKeyBanner>` component (AC: 3, 4, UX-DR6)
  - [ ] `role="alert"` — screen readers announce appearance
  - [ ] "Copy this key now — it won't be shown again." instruction
  - [ ] Copy button: `aria-label="Copy API key to clipboard"`, 2-second "Copied ✓" feedback
  - [ ] `shadow-sm` visual prominence

- [ ] Task 5: Create `<ApiKeyList>` component (AC: 1, 2, 5, 6, UX-DR5)
  - [ ] Table structure with `<th scope="col">` headers
  - [ ] Key preview: `font-mono text-xs text-gray-600`
  - [ ] Revoke button: `text-sm text-red-600 hover:text-red-700` (no background, no confirm modal)
  - [ ] Revoking in-flight per-row state
  - [ ] Empty state message

- [ ] Task 6: Create `<ApiKeysView>` container component (AC: 1–6)
  - [ ] `useEffect` on mount: fetch key list via `listKeys()`
  - [ ] State: `keys`, `newKey` (for banner), `revokingId`
  - [ ] Compose `<GenerateKeyButton>`, `<NewKeyBanner>`, `<ApiKeyList>`

- [ ] Task 7: Wire `<ApiKeysView>` into `App.tsx` (AC: 1)
  - [ ] Replace `<div>API Keys</div>` stub with `<ApiKeysView />`

- [ ] Task 8: Verify locally (AC: 1–8)
  - [ ] `npm run dev` → navigate to API Keys → confirm list loads
  - [ ] Generate a key → confirm banner appears with full key
  - [ ] Copy key → confirm "Copied ✓" feedback
  - [ ] Revoke a key → confirm it disappears from the list
  - [ ] `npm run build` → exits 0

## Dev Notes

### Prerequisites

- Story 2.2 must be complete: `POST /api/keys`, `GET /api/keys`, `DELETE /api/keys/{key_id}` deployed to Railway
- Story 2.4 must be complete: `<Sidebar>` renders and `activeView === 'keys'` switch works
- `src/lib/supabase.ts` must exist (Story 2.3)
- Railway API must be running and `VITE_API_BASE_URL` set

### API Client — `src/lib/api.ts`

```typescript
// src/lib/api.ts
import { supabase } from './supabase'

const API_BASE = import.meta.env.VITE_API_BASE_URL as string

// ── Types matching Story 2.2 Pydantic schemas (snake_case) ──────────────────

export interface ApiKeyCreateResponse {
  id: string
  key: string        // full plaintext — only present at creation
  key_prefix: string
  created_at: string // ISO 8601
}

export interface ApiKeyListItem {
  id: string
  key_prefix: string
  created_at: string // ISO 8601
}

// ── Auth helper ──────────────────────────────────────────────────────────────

async function authHeaders(): Promise<HeadersInit> {
  const { data: { session } } = await supabase.auth.getSession()
  if (!session?.access_token) throw new Error('Not authenticated')
  return {
    'Authorization': `Bearer ${session.access_token}`,
    'Content-Type': 'application/json',
  }
}

// ── API functions ─────────────────────────────────────────────────────────────

export async function generateKey(): Promise<ApiKeyCreateResponse> {
  const res = await fetch(`${API_BASE}/api/keys`, {
    method: 'POST',
    headers: await authHeaders(),
  })
  if (!res.ok) throw new Error(`Generate failed: ${res.status}`)
  return res.json() as Promise<ApiKeyCreateResponse>
}

export async function listKeys(): Promise<ApiKeyListItem[]> {
  const res = await fetch(`${API_BASE}/api/keys`, {
    headers: await authHeaders(),
  })
  if (!res.ok) throw new Error(`List failed: ${res.status}`)
  return res.json() as Promise<ApiKeyListItem[]>
}

export async function revokeKey(keyId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/keys/${keyId}`, {
    method: 'DELETE',
    headers: await authHeaders(),
  })
  if (!res.ok) throw new Error(`Revoke failed: ${res.status}`)
  // 204 No Content — no body to parse
}
```

**Why `Content-Type: application/json` on DELETE?**
FastAPI doesn't need it for DELETE but including it consistently in all requests is safe and harmless.

**Why not axios?**
`fetch` is built into the browser, already available, and sufficient for three simple calls. Adding axios adds ~15KB to the bundle for no benefit at this scale.

### `<GenerateKeyButton>` Component

```tsx
// src/components/GenerateKeyButton.tsx
import { useState } from 'react'
import { generateKey, ApiKeyCreateResponse } from '../lib/api'

interface GenerateKeyButtonProps {
  onKeyGenerated: (key: ApiKeyCreateResponse) => void
}

export function GenerateKeyButton({ onKeyGenerated }: GenerateKeyButtonProps) {
  const [isGenerating, setIsGenerating] = useState(false)

  async function handleClick() {
    setIsGenerating(true)
    try {
      const newKey = await generateKey()
      onKeyGenerated(newKey)
    } catch (err) {
      console.error('Failed to generate key', err)
    } finally {
      setIsGenerating(false)
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={isGenerating}
      className={[
        'bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-2 px-4 rounded',
        'transition-colors duration-150',
        'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2',
        isGenerating ? 'opacity-75 cursor-not-allowed' : '',
      ].join(' ')}
    >
      {isGenerating ? 'Generating...' : 'Generate new key'}
    </button>
  )
}
```

### `<NewKeyBanner>` Component

```tsx
// src/components/NewKeyBanner.tsx
import { useState } from 'react'

interface NewKeyBannerProps {
  apiKey: string  // full plaintext key
}

export function NewKeyBanner({ apiKey }: NewKeyBannerProps) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    await navigator.clipboard.writeText(apiKey)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div
      role="alert"
      className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm space-y-3"
    >
      <p className="text-sm font-medium text-gray-900">
        Copy this key now — it won't be shown again.
      </p>
      <div className="flex items-center gap-3">
        <code className="flex-1 font-mono text-xs text-gray-600 bg-gray-50 border border-gray-200 rounded px-3 py-2 break-all">
          {apiKey}
        </code>
        <button
          onClick={handleCopy}
          aria-label="Copy API key to clipboard"
          className={[
            'flex-shrink-0 text-sm font-medium px-3 py-2 rounded border border-gray-200',
            'bg-white hover:bg-gray-100 text-gray-700',
            'transition-colors duration-150',
            'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2',
          ].join(' ')}
        >
          {copied ? 'Copied ✓' : 'Copy'}
        </button>
      </div>
    </div>
  )
}
```

**`role="alert"` makes `<NewKeyBanner>` announced immediately** when it mounts. Screen readers read the content without the user needing to navigate to it — critical for accessibility since the key is only shown once.

**`shadow-sm`** — provides the visual prominence called out in UX-DR6.

**`setTimeout(() => setCopied(false), 2000)`** — the cleanup is synchronous; no need to clear the timeout since the 2-second window is intentionally self-resetting.

### `<ApiKeyList>` Component

```tsx
// src/components/ApiKeyList.tsx
import { useState } from 'react'
import { revokeKey, ApiKeyListItem } from '../lib/api'

interface ApiKeyListProps {
  keys: ApiKeyListItem[]
  onKeyRevoked: (keyId: string) => void
}

export function ApiKeyList({ keys, onKeyRevoked }: ApiKeyListProps) {
  const [revokingId, setRevokingId] = useState<string | null>(null)

  async function handleRevoke(keyId: string) {
    setRevokingId(keyId)
    try {
      await revokeKey(keyId)
      onKeyRevoked(keyId)
    } catch (err) {
      console.error('Failed to revoke key', err)
    } finally {
      setRevokingId(null)
    }
  }

  if (keys.length === 0) {
    return (
      <p className="text-sm text-gray-500">
        No API keys yet. Generate one to connect your CLI.
      </p>
    )
  }

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-gray-200">
          <th scope="col" className="text-left text-xs font-medium text-gray-500 uppercase tracking-widest pb-2 pr-4">
            Key
          </th>
          <th scope="col" className="text-left text-xs font-medium text-gray-500 uppercase tracking-widest pb-2 pr-4">
            Created
          </th>
          <th scope="col" className="text-left text-xs font-medium text-gray-500 uppercase tracking-widest pb-2">
            <span className="sr-only">Actions</span>
          </th>
        </tr>
      </thead>
      <tbody className="divide-y divide-gray-200">
        {keys.map((key) => (
          <tr key={key.id}>
            <td className="py-3 pr-4">
              <span className="font-mono text-xs text-gray-600">{key.key_prefix}...</span>
            </td>
            <td className="py-3 pr-4 text-sm text-gray-500">
              {new Date(key.created_at).toLocaleDateString()}
            </td>
            <td className="py-3">
              <button
                onClick={() => handleRevoke(key.id)}
                disabled={revokingId === key.id}
                className={[
                  'text-sm text-red-600 hover:text-red-700',
                  'transition-colors duration-150',
                  'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 rounded',
                  revokingId === key.id ? 'opacity-50 cursor-not-allowed' : '',
                ].join(' ')}
              >
                {revokingId === key.id ? 'Revoking...' : 'Revoke'}
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
```

**Why `revokingId` per-row instead of a `Set<string>`?**
At V1 usage (solo developer, a handful of keys), only one revoke will ever be in-flight at a time. A single `string | null` is simpler than managing a Set.

**`<th scope="col">`** — required by UX-DR5 and WCAG for table accessibility.

**"Actions" column uses `<span className="sr-only">`** — visible headers for the first two columns; the actions column is self-explanatory visually but needs a header for screen readers.

### `<ApiKeysView>` Container

```tsx
// src/components/ApiKeysView.tsx
import { useEffect, useState } from 'react'
import { listKeys, ApiKeyCreateResponse, ApiKeyListItem } from '../lib/api'
import { GenerateKeyButton } from './GenerateKeyButton'
import { NewKeyBanner } from './NewKeyBanner'
import { ApiKeyList } from './ApiKeyList'

export function ApiKeysView() {
  const [keys, setKeys] = useState<ApiKeyListItem[]>([])
  const [newKey, setNewKey] = useState<ApiKeyCreateResponse | null>(null)

  useEffect(() => {
    listKeys()
      .then(setKeys)
      .catch((err) => console.error('Failed to load keys', err))
  }, [])

  function handleKeyGenerated(created: ApiKeyCreateResponse) {
    setNewKey(created)
    // Add to the list immediately (optimistic update — no re-fetch needed)
    setKeys((prev) => [
      { id: created.id, key_prefix: created.key_prefix, created_at: created.created_at },
      ...prev,
    ])
  }

  function handleKeyRevoked(keyId: string) {
    setKeys((prev) => prev.filter((k) => k.id !== keyId))
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">API Keys</h1>
        <GenerateKeyButton onKeyGenerated={handleKeyGenerated} />
      </div>

      {newKey && <NewKeyBanner apiKey={newKey.key} />}

      <ApiKeyList keys={keys} onKeyRevoked={handleKeyRevoked} />
    </div>
  )
}
```

**Optimistic update after generation** — rather than re-fetching the key list after POST, extract the key metadata from the response and prepend it locally. This avoids an extra round-trip and makes the UI feel instant.

**`newKey` state persists for the session** — once the banner appears, it stays until navigation away. The user can copy the key at their own pace without it disappearing. UX spec says "shown once at creation" — this means shown once per creation event, not disappearing after N seconds.

### Update `App.tsx`

Replace the `<div>API Keys</div>` stub:

```tsx
// In App.tsx authenticated section:
import { ApiKeysView } from './components/ApiKeysView'

// In the return:
{activeView === 'dashboard' ? (
  <div>Dashboard</div>
) : (
  <ApiKeysView />
)}
```

### Set `VITE_API_BASE_URL` in Local Dev and Vercel

**Local dev** — add to `web/.env.local`:
```
VITE_API_BASE_URL=https://your-api.up.railway.app
```

**Vercel** — Settings → Environment Variables → add:
- `VITE_API_BASE_URL` = `https://your-api.up.railway.app`

Without this, all `fetch` calls will fail with `TypeError: Failed to fetch` because the base URL is `undefined`.

### CORS — Railway API Must Allow Vercel Origin

When the browser calls the Railway API from the Vercel domain, Railway's CORS policy must allow it. FastAPI does not have CORS enabled by default. This needs to be added to `main.py`:

```python
# src/opentaion_api/main.py — add CORS middleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentaion_api.routers import keys

app = FastAPI(title="opentaion-api", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-app.vercel.app",  # replace with actual Vercel URL
        "http://localhost:5173",         # local dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(keys.router, prefix="/api")

@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
```

**Add `CORS_ORIGINS` as a Railway env var** for flexibility:
```python
import os
origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(CORSMiddleware, allow_origins=origins, ...)
```

Then set in Railway: `CORS_ORIGINS=https://your-app.vercel.app,http://localhost:5173`

**This is a required change to `api/src/opentaion_api/main.py`** — without it, the browser blocks all API calls from the Vercel origin.

### Design Token Compliance

| Element | Classes | Requirement |
|---|---|---|
| Page heading | `text-xl font-semibold text-gray-900` | UX-DR9: page heading scale |
| Table column headers | `text-xs font-medium text-gray-500 uppercase tracking-widest` | UX-DR9: section label scale |
| Key preview | `font-mono text-xs text-gray-600` | UX-DR5: monospace key display |
| Revoke button | `text-sm text-red-600 hover:text-red-700` | UX-DR5, UX-DR12: destructive text button |
| Generate button | `bg-blue-600 hover:bg-blue-700 text-white` | UX-DR12: primary button |
| Empty state | `text-sm text-gray-500` | UX-DR9: metadata/secondary text |
| Banner | `shadow-sm` | UX-DR6: visual prominence |

### Architecture Cross-References

From `ux-design-specification.md`:
- UX-DR5: `<ApiKeyList>` — `font-mono text-xs text-gray-600`, `text-red-600`, three states, `<th scope="col">` [Source: ux-design-specification.md#Component Strategy]
- UX-DR6: `<NewKeyBanner>` — `role="alert"`, copy button `aria-label`, 2s feedback, `shadow-sm` [Source: ux-design-specification.md#Component Strategy]
- UX-DR7: `<GenerateKeyButton>` — "Generating..." loading state, `opacity-75 cursor-not-allowed`, `onKeyGenerated` callback [Source: ux-design-specification.md#Component Strategy]

From `epics.md`:
- FR2: "Developer can generate a new OpenTalon API key from the web dashboard (displayed once at creation)" [Source: epics.md#FR2]
- FR3: "Developer can view a list of their active API keys with a truncated preview" [Source: epics.md#FR3]
- FR4: "Developer can revoke an API key by ID from the web dashboard" [Source: epics.md#FR4]
- NFR5: "A generated API key must be displayed exactly once at creation; it must not be retrievable after the creation response" [Source: epics.md#NFR5]

### What This Story Does NOT Include

- The `opentaion login` CLI command that uses the generated key (Story 2.6)
- Dashboard view with usage charts (Story 4.2)
- Error handling UI for failed API calls beyond `console.error` — V1 scope
- Loading skeleton while keys are fetching — V1 scope
- Key creation date formatted as relative time ("3 days ago") — V1 uses `toLocaleDateString()`

### Final Modified/Created Files

```
api/src/opentaion_api/
└── main.py               # MODIFIED — add CORS middleware

web/src/
├── App.tsx               # MODIFIED — replace <div>API Keys</div> with <ApiKeysView />
├── lib/
│   ├── supabase.ts       # unchanged
│   └── api.ts            # NEW — fetch wrappers + TypeScript types
└── components/
    ├── ApiKeysView.tsx    # NEW — container with state management
    ├── ApiKeyList.tsx     # NEW — table with revoke buttons
    ├── NewKeyBanner.tsx   # NEW — one-time key display with copy
    └── GenerateKeyButton.tsx  # NEW — generate button with loading state
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
