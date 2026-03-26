// src/lib/api.ts
import { supabase } from './supabase'

const API_BASE = import.meta.env.VITE_API_BASE_URL
if (!API_BASE) {
  throw new Error('Missing VITE_API_BASE_URL')
}

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

export async function fetchUsage(signal?: AbortSignal): Promise<import('../types/api').UsageResponse> {
  const res = await fetch(`${API_BASE}/api/usage`, {
    headers: await authHeaders(),
    signal,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<import('../types/api').UsageResponse>
}
