// src/components/ApiKeyList.tsx
import { useState } from 'react'
import { revokeKey, ApiKeyListItem } from '../lib/api'

interface ApiKeyListProps {
  keys: ApiKeyListItem[]
  onKeyRevoked: (keyId: string) => void
}

export function ApiKeyList({ keys, onKeyRevoked }: ApiKeyListProps) {
  const [revokingIds, setRevokingIds] = useState<Set<string>>(new Set())

  async function handleRevoke(keyId: string) {
    setRevokingIds((prev) => new Set(prev).add(keyId))
    try {
      await revokeKey(keyId)
      onKeyRevoked(keyId)
    } catch (err) {
      console.error('Failed to revoke key', err)
    } finally {
      setRevokingIds((prev) => { const next = new Set(prev); next.delete(keyId); return next })
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
                disabled={revokingIds.has(key.id)}
                className={[
                  'text-sm text-red-600 hover:text-red-700',
                  'transition-colors duration-150',
                  'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 rounded',
                  revokingIds.has(key.id) ? 'opacity-50 cursor-not-allowed' : '',
                ].join(' ')}
              >
                {revokingIds.has(key.id) ? 'Revoking...' : 'Revoke'}
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
