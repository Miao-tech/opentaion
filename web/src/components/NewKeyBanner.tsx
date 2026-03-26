// src/components/NewKeyBanner.tsx
import { useRef, useState } from 'react'

interface NewKeyBannerProps {
  apiKey: string  // full plaintext key
}

export function NewKeyBanner({ apiKey }: NewKeyBannerProps) {
  const [copied, setCopied] = useState(false)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(apiKey)
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
      setCopied(true)
      timeoutRef.current = setTimeout(() => setCopied(false), 2000)
    } catch {
      // Clipboard unavailable (no HTTPS, permission denied, document unfocused)
      // Button stays at "Copy" — user can copy manually from the code element
    }
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
