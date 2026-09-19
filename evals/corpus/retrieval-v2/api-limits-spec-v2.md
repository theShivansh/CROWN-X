## Spec v2 · Endpoints
FestPass API and limits, version 2.0, updated 14 September 2026. `GET /events` lists the Autumn Fest
events with their remaining seats. `POST /registrations` registers a student for one event and returns
the pass ID. `GET /passes/{id}` returns the QR pass. New in version 2: `POST /payments/intent` starts a
payment for a paid workshop.

## Spec v2 · Events Portal limit
FestPass reads event data from the college Events Portal with the team's API key. IT Services lowered
the Events Portal API rate limit from 100 to 60 requests per minute per team API key on 10 September.
Requests above the limit get HTTP 429 and count against the same minute.

## Spec v2 · Our own API throttling
The FestPass API throttles its own callers so one misbehaving phone can't starve everyone else. API
Gateway allows 20 requests per second per client IP with a burst of 40, and returns HTTP 429 above
that. The registration endpoint is further limited to 5 requests per minute per roll number.

## Spec v2 · Retries and backoff
On a 429 from the Events Portal, FestPass retries with exponential backoff, starting at one second and
giving up after four attempts. On a 5xx from the portal it shows the last cached event list with a
notice that seat counts may be out of date.

## Spec v2 · Payload limits
Request bodies stay under 4 KB. A registration carries the student's roll number, name, email, phone
and the event ID. Event posters uploaded by organisers may be up to 2 MB, in PNG or JPEG only, and are
resized to 1,200 pixels wide before they are published.
