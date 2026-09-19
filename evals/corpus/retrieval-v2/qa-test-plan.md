## QA · Scope
The QA plan, owned by Dev Malhotra, covers four flows: finding an event, registering with an OTP,
opening the QR pass, and scanning it at the gate. The live seat count is checked in each flow. Payments
are not tested because they were dropped at Sync 6.

## QA · Device matrix
Tests run on Android 10 and later and iOS 15 and later, in Chrome and Safari. The low-end reference
phone is a Redmi 9A, since many first-year students use similar phones, and every page must be usable
on its screen and processor.

## QA · Load testing
Load tests use k6 against the staging stack. The target is 500 concurrent virtual users registering
for ten minutes, and the pass criterion is a p95 latency under 800 ms with fewer than 1% errors other
than expected throttling.

## QA · Regression suite
The regression suite has 84 automated tests: unit tests for the pass signature and the seat counter,
and API tests for every endpoint. It runs in GitHub Actions on every push, and a failing suite blocks
the merge to the main branch.

## QA · Bug triage
Bugs are labelled P1 when they block registration, scanning or the seat count, and P2 otherwise. P1
bugs are fixed within 24 hours; P2 bugs are fixed before the demo freeze or listed as known issues in
the README.
