# Final UI and browser review

Locally vendored Bootstrap 5.3.3 and local CSS require no external fonts/scripts/
network assets. Vendor copyright/license is retained. Navigation/active states,
role labels, student navigation, dashboards, forms, inline error associations,
column headers, empty/recovery states and mobile scrolling use a navy/teal theme.
Skip links and keyboard focus styling are included; core workflows require no JS.

Real Chromium headless QA: desktop 1440x1000 and mobile 390x844, all non-local
requests blocked. Pages returned 200; no page errors/external requests/whole-page
horizontal overflow. Invalid profile submission showed aria-associated errors
without changing its row. Password values were not captured. Server stopped.

- [Desktop homepage](screenshots/desktop-home.png)
- [Mobile homepage](screenshots/mobile-home.png)
- [Desktop finances](screenshots/desktop-financial.png)
- [Mobile finances](screenshots/mobile-financial.png)
- [Student dashboard](screenshots/desktop-student-dashboard.png)
- [Mobile validation](screenshots/mobile-validation.png)

Sixteen screenshots cover home/events/clubs, student/admin dashboards, validation,
finance/participation at both sizes. Desktop finance and mobile home were also
inspected visually. Practical QA is not a claim of complete accessibility or
usability certification. The browser verifier can regenerate its machine-readable output when needed;
that development JSON output is not retained in the cleaned source tree.
