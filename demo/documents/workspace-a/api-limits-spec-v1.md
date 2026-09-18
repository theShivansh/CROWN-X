FestPass API and limits · Version 1.0 · Last updated: 3 Sept 2026

# FestPass API and limits

## Endpoints
- `GET /events`: the Autumn Fest events with their remaining seats, read from the Events Portal.
- `POST /registrations`: registers a student for one event and returns the pass ID.
- `GET /passes/{id}`: the QR pass for a registration.

## Payloads
Request bodies stay under 4 KB. A registration carries the student's roll number, name, email and the
event ID. Pass images are generated on request and never stored.

## Events Portal
FestPass reads event data from the college Events Portal with the team's API key.

Events Portal API rate limit: 100 requests per minute per team API key.

## Errors and retries
On a 429 from the Events Portal, FestPass retries with exponential backoff, starting at one second and
giving up after four attempts. On a 5xx it shows the last cached event list with a notice.
