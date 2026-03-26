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
    if (newKey?.id === keyId) setNewKey(null)
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
