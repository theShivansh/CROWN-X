## Retro · What went well
Team Lantern retrospective after the first sprint week, 12 September 2026. The QR scanning prototype
worked on real phones by day three, the brief was agreed early, and splitting the frontend and backend
between Ishita and Rohan kept merges small.

## Retro · What went badly
We lost two days. Each of us ran the app locally against the real Events Portal, the portal started
refusing our requests, and then it went down for everyone during the college's outage. Nobody noticed
that our key had been blocked until the next morning.

## Retro · Root cause of the portal block
Every developer's local copy polled the portal for the event list every five seconds. Four laptops
together sent far more than the portal allows for one team key, so IT Services blocked the key for six
hours. The block, not the outage, cost us the first day.

## Retro · Changes we agreed
Cache the event list on the server instead of polling from each client. Use one shared staging key
with a mock portal for local development. Add an alert when the portal returns 429, so a block is
noticed within minutes rather than the next day.

## Retro · Team health
Energy is good, but Dev is carrying both QA and the meeting notes. From Sync 6, note-taking rotates
between all four of us, and Dev keeps QA.
