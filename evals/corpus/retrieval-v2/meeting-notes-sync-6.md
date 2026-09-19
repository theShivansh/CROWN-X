## Sync 6 · Attendance
Team Lantern, Sync 6, Wednesday 16 September 2026. Present: Ananya Iyer, Rohan Mehta, Ishita Rao and
Dev Malhotra. Guest: Sana Sheikh from the Innovation Cell, who joined for the first twenty minutes to
answer questions about judging. Notes by Dev.

## Sync 6 · Payment gateway spike
Rohan reported on the payment gateway spike. The Razorpay sandbox works end to end in test mode, but
going live needs the college's KYC documents, which won't arrive before the fest. Decision: paid
workshops will not take payments through FestPass this year; organisers collect fees at the desk.

## Sync 6 · Load test results
Dev ran the first load test against staging: 500 concurrent virtual users registering for events for
ten minutes. The p95 latency was 380 ms and the error rate 0.4%, all of it HTTP 429 from our own API
throttling on one shared test IP, which is expected.

## Sync 6 · Decisions
Demo freeze on 21 September at 18:00: after that only bug fixes are merged. The demo video will show
registration, the QR pass and door scanning, in that order. Ananya presents; Ishita drives the demo.

## Sync 6 · Action items
Dev writes the demo script by Friday. Ishita sets a CloudWatch alarm when the 5xx rate stays above 2%
for five minutes. Rohan writes up the payment spike for the README. Ananya asks Prof. Kulkarni about
certificates for volunteers.
