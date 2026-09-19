## Architecture · Hosting
FestPass runs on AWS in the Mumbai region, ap-south-1. The student site is a static Next.js export on
AWS Amplify. The API is a set of Lambda functions behind API Gateway, and registrations, passes and
seat counts live in DynamoDB. Ishita Rao owns the AWS account and the deployment pipeline.

## Architecture · Event list cache
The Events Portal only allows 60 requests per minute per team key, and every open FestPass page used
to ask it for the event list. The API now keeps the event list in a DynamoDB item with a five-minute
TTL and refreshes it from the portal only when the item has expired. Seat counts are ours, so they are
never cached.

## Architecture · QR pass generation
A pass is a QR code that encodes the pass ID, the event ID and an HMAC signature over both. Pass images
are generated on request from those three values and never stored, so a leaked image bucket can't
exist. The signing key is loaded from Secrets Manager when a Lambda starts.

## Architecture · Offline door scanning
The volunteer scanner app downloads the day's pass list and the verification key at the start of each
shift. It checks signatures and marks entries locally, so scanning keeps working when the gate loses
its network connection, and it syncs the entries back to the API as soon as it is online again.

## Architecture · Data retention
Registration records hold a roll number, name, email and phone number. They are deleted 30 days after
Autumn Fest ends, and the seat counts are kept only as anonymous totals per event. CloudWatch logs are
retained for 14 days and never contain a phone number or an email address.
