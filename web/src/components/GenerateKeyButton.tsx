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
