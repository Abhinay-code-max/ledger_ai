# Verification — 16 October 2026

The supplied workspace was empty and the only attachment was the brief. No existing source, identity backend, financial integrations, original logo, or measured AMD benchmark results were available.

## Completed checks

- TypeScript checking and Vite production build passed.
- The intro appeared separately, removed itself after completion, restored scrolling, and did not replay when returning home within the same browser session.
- The homepage rendered a real WebGL canvas and contained no authentication forms.
- The static-view control removed the hero canvas, displayed accessible fallback content, and restored interactive 3D when requested.
- All six workflow controls displayed the correct stage, explanation, and evidence state.
- Capability selection opened its associated explanation and illustrative evidence path.
- The product showcase exception filter returned one seeded exception. Its detail dialog displayed the source references, focused its close control, and closed with Escape.
- Login navigation displayed three large role cards and separate sign-in forms.
- With no identity backend configured, sign-in stayed on the login route with an explanatory message. Direct protected-route access exposed no demo table or operational records.
- Administrator demo tabs displayed three sample users, six sample audit events, and an empty verified-benchmark state without invented measurements.
- Manager demo approval changed a pending record and removed it from the pending approval queue.
- Employee document search returned the matching record. Supplier corrections saved into the local demo record when marked reviewed.
- Character-by-character correction input retained keyboard focus. Escape closed the review drawer and restored body scrolling.
- A local CSV test fixture added filename metadata to the employee demo. The interface confirmed that no file was transmitted or analyzed.
- Task routing classified an access request to Administrator, explained the keyword rule, showed priority and unavailable model confidence, required confirmation, and added a local demo task.
- At a 390 × 844 CSS viewport, mobile navigation opened and linked to the workflow; workflow controls worked, role cards formed one column, and dashboard task controls remained usable. No horizontal document overflow was observed. The temporary viewport override was reset.
- Browser console checks returned no warnings or errors in the verification tabs.
- Source files contain no explanatory code comments.

## Limits

Production identity success, server-side permissions, live financial operations, model inference, accounting posting, source preservation, and original-logo fidelity could not be verified without the missing inputs. The production dashboard deliberately shows an integration-required empty state after identity verification; operational sample data only appears in demo routes.

The automatic context-loss fallback and operating-system reduced-motion behavior were reviewed in source but were not forced through browser emulation. The manually selected static view was exercised. No representative hardware frame-rate, mobile GPU, or accessibility certification measurement was performed.

Vite reports a large Three.js vendor chunk, approximately 314 kB compressed. It is loaded through the lazy scene module; the lower-page scene mounts near the viewport, offscreen scenes pause, tick geometry is instanced, and device pixel ratio is limited. The warning remains visible rather than being suppressed.

Screenshots in `qa/` document the desktop homepage, workflow, role selection, dashboard, and mobile views. Demo changes are held in component state and reset on reload; no actual financial records were changed.
