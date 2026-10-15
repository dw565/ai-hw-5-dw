# Campus Customs Operations Desk (frontend)

A steampunk React + Vite + TypeScript dashboard for the Campus Customs agent team. It talks to the FastAPI backend at `http://localhost:8000`; override that with `VITE_API_BASE`.

```bash
npm install
npm run dev     # http://localhost:5173
```

Start the backend first, from `../backend`: `uvicorn main:app --reload --port 8000`.

- `src/api.ts`: typed client for the backend routes.
- `src/useDesk.ts`: polling and state (tickets, cash, payments, incremental events, run status).
- `src/agents.tsx`: per-agent identity (ink color, title, emblem).
- `src/components/`: `CashGauge`, `TicketList`, `AgentRoster`, `ActivityFeed`, `Approvals`, `AgentSummary`, `Emblems` (SVG art).

Design notes: `../output/design.md`.
