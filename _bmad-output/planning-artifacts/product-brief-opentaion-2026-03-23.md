# OpenTalon Product Brief

## Market Context
Solo developers and small teams using AI coding assistants
face a usage transparency problem. LLM API costs are opaque
until billing time. There is no lightweight, self-hostable
tool that provides real-time usage visibility.

## User Persona
**The Budget-Conscious Solo Developer**
- Technical user (Python/JavaScript primary)
- Uses 1-3 AI coding assistants regularly
- Budget-sensitive: prefers free or low-cost options
- Self-hosting preference: will run a local API over paying SaaS
- Pain point: bill anxiety limits AI adoption

## Core Problem Statement
Developers cannot make informed decisions about AI tool usage
because they have no visibility into token consumption until
the invoice arrives. This creates a binary outcome: use AI
freely and risk overage, or self-limit and underutilize a
productivity tool.

## Proposed Solution
OpenTalon: a macOS CLI agent with a companion web dashboard.
The CLI routes all LLM calls through a local proxy (the API
component) that meters usage in real time. The dashboard
displays daily and per-model token consumption.

## Success Metrics
- Developer checks dashboard at least once per week
- Developer reports no billing surprises after first month
- CLI adds < 200ms latency to LLM call response time

## Risks
- Proxy latency may be unacceptable for interactive use
- Self-hosting friction may limit adoption for less technical users
