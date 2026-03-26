// src/components/Sidebar.tsx
import { useState } from 'react'
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
  const [signingOut, setSigningOut] = useState(false)

  async function handleSignOut() {
    setSigningOut(true)
    const { error } = await supabase.auth.signOut()
    if (error) {
      console.error('Sign out failed:', error.message)
      setSigningOut(false)
    }
    // On success, onAuthStateChange in App.tsx sets user to null — no state reset needed here.
  }

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
            type="button"
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
          type="button"
          onClick={handleSignOut}
          disabled={signingOut}
          className="w-full text-left px-3 py-2 rounded-md text-sm text-gray-500 hover:bg-gray-50 transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {signingOut ? 'Signing out...' : 'Sign out'}
        </button>
      </div>
    </aside>
  )
}
