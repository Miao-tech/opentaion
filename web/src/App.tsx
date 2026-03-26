// src/App.tsx
import { useEffect, useState } from 'react'
import type { User } from '@supabase/supabase-js'
import { supabase } from './lib/supabase'
import { LoginForm } from './components/LoginForm'
import { Sidebar } from './components/Sidebar'
import { ApiKeysView } from './components/ApiKeysView'
import Dashboard from './Dashboard'

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
      if (session?.user) setActiveView('dashboard')
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
          <Dashboard />
        ) : (
          <ApiKeysView />
        )}
      </main>
    </div>
  )
}

export default App
