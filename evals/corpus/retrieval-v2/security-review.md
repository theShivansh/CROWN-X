## Security · Threat summary
Security review of FestPass by Rohan Mehta and Dev Malhotra, 13 September 2026. The three risks that
matter most are forged or copied passes at the gate, scraping of students' personal data through the
API, and abuse of the OTP step to send large numbers of text messages at our expense.

## Security · Pass forgery
A photocopied or screenshotted pass is only useful once: the scanner app marks a pass as used on
first entry and rejects a second scan. A forged pass fails because its HMAC signature doesn't verify,
and the signing key is rotated for each fest.

## Security · OTP abuse
A phone number can request at most 3 OTP messages per hour, and a CAPTCHA appears after the second
request. The API refuses OTP requests for numbers that aren't Indian mobile numbers, which blocks the
common international SMS-pumping attack.

## Security · Personal data
FestPass stores each student's roll number, name, email and phone number. The table is encrypted at
rest, and only the organisers' role can read it; volunteers see a pass ID and a first name, never a
phone number or an email address.

## Security · Secrets
The Events Portal key and the pass signing key live in AWS Secrets Manager, never in the repository.
The portal key was rotated on 14 September after it was pasted into the team chat by mistake, and the
old key was revoked by IT Services the same day.
