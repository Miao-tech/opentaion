# Web — Component Rules

## Environment
- Node.js 20+. Framework: Vite 5 + React 18 + TypeScript (strict)
- Dev server: `npm run dev`
- Build: `npm run build`
- Tests: `npm run test` (vitest)

## Component conventions
- Functional components with explicit TypeScript prop types
- Local state: useState only — no external state management
- Styling: Tailwind utility classes only — no separate CSS files
- Charts: Recharts library for all data visualization
- No routing library — conditional rendering based on Supabase auth state

## Anti-patterns (IMPORTANT)
- Never use inline styles — Tailwind classes only
- Never reach into api/ or cli/ from web code
- Never add an npm package if Tailwind or Recharts already covers the need