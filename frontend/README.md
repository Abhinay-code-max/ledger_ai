# ledgar.ai

A React, TypeScript and Vite frontend for an interactive finance operations website, with a procedural 3D scene, a six-stage workflow, role-specific sign-in and illustrative workspaces.

## Run locally

Use a current Node.js release supported by Vite 7, then run:

```sh
npm install
npm run dev
```

Vite prints the local address. Create `.env.local` from `.env.example` if you want to configure the authentication API, then restart the development server after changing it.

```sh
npm run build
npm run preview
```

`npm run build` runs TypeScript checking and produces the static site in `dist`. A production host must serve `index.html` for client routes such as `/login/manager` and `/demo/employee`.

## Supplied inputs and branding

The workspace contained no original website source and the only supplied attachment was the brief; no logo was available. This is a new frontend implementation rather than a modification of a supplied application. The mark and wordmark in `src/components/Brand.tsx`, the favicon and the workflow illustration's small wordmark are provisional assets. Put an approved logo in `public/` and set `VITE_LOGO_URL=/your-logo.svg` to use that exact image in the shared brand component and intro. Replace the favicon and illustration mark separately. Procedural 3D geometry and interface illustrations do not imply a supplied product screenshot or a connected financial system.

The site uses DM Sans and Manrope through Google Fonts with local fallback fonts. An offline deployment can self-host those fonts or use the fallbacks.

## Routes and demonstrations

| Route | Purpose |
| --- | --- |
| `/` | Marketing website and interactive walkthrough |
| `/login` | Choose the sign-in experience for a role |
| `/login/admin` | Administrator sign-in |
| `/login/manager` | Finance manager sign-in |
| `/login/employee` | Finance employee sign-in |
| `/dashboard/:role` | Session-verified workspace entry |
| `/demo/:role` | Explicitly labeled, browser-only demonstration |

Demo records, invoice values, processing counts, reviewer identities and evidence paths are seeded examples. Demo interactions illustrate the intended experience; they do not post accounting records, reconcile a live ledger, send approvals to a server or establish production audit evidence. Any local file-selection experience is illustrative. No live backend is included in this repository.

There are no verified accuracy, performance, throughput, compliance or certification claims. Interface numbers and labels are examples rather than benchmark results. AI interpretation, deterministic matching and human approval are presented as separate responsibilities.

## Authentication integration

Set the public configuration value `VITE_API_BASE_URL` to the base URL of your own identity backend. Leave it empty to keep production authentication unavailable. It is embedded in the browser build and must never contain a secret. Demo access remains separate from production sign-in.

The expected backend contract is:

| Endpoint | Expected behavior |
| --- | --- |
| `POST /auth/login` | Accept JSON containing `email`, `password` and the requested `role`. Authenticate the identity, check its permitted role and create a server session. |
| `GET /auth/me` | Validate the current session and return the authenticated user and its server-authorized role. Return an authorization error for an absent or expired session. |

The frontend expects a session user in this form; `role` must be one of `admin`, `manager` or `employee`:

```json
{
  "user": {
    "id": "server-user-id",
    "name": "Alex Morgan",
    "email": "alex@example.com",
    "role": "manager"
  }
}
```

The requested role is a sign-in context, never a grant of permission. The backend must reject unauthorized role choices, and the server-returned role must determine the authenticated workspace. A successful-looking login response alone must not bypass the session check.

Use HTTPS and an appropriately configured session cookie, including `HttpOnly`, `Secure` and a suitable `SameSite` policy. If the API is cross-origin, configure its allowed origin and credential handling for the deployed frontend. Implement CSRF protection appropriate to the session design, server-side authorization, rate limiting, logout, password recovery and identity management in the backend. Those services are not provided by this frontend.

Client route guards, hidden controls and role-specific navigation do not protect financial data. Every server endpoint must independently check the session, role, organization and object-level permissions. Real uploads, AI services, accounting integrations, reconciliation, approval posting, reporting and audit storage need authenticated backend implementations and production validation. Connect only a backend you control, and use test accounts until that integration has been verified.

## Interaction and accessibility

The website supports keyboard controls, visible focus indicators, mobile layouts, reduced-motion preferences and a 3D fallback. The six workflow stages can be selected directly; automatic scroll progression pauses while a workflow control has focus and is disabled for reduced motion. The opening animation has a skip control and is remembered for the current browser session.

Before deploying, test the final branded content and backend integration with your supported browsers, assistive technologies and device sizes. This repository does not claim a completed accessibility certification or production security audit.
