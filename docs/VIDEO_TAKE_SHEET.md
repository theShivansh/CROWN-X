# Video take sheet (3:00 or less)

The form asks the video to cover four things: **about the project, the tech stack and architecture,
how AWS is used, and learning.** The script below does all four in order. Record in one take if you
can. Two takes, joined at 1:55 (before "AWS"), also works.

## Setup (5 minutes before)
- **Window.** Chrome at 1440x900, browser zoom 110%, dark OS theme. Close bookmarks and extensions
  that draw on the page.
- **Screen recorder.** OBS or Win+G, 1080p, microphone checked.
- **Tabs, left to right:**
  1. **App, workspace A** (the demo):
     https://main.d1jy52bqj8dt1h.amplifyapp.com/app/?ws=ws_KFdHFNj0IPUoOs4pQDcMUQ
  2. **"Not found" link, for the error drill:**
     https://main.d1jy52bqj8dt1h.amplifyapp.com/app/?ws=ws_videoDrillNotFound0000
  3. **README on GitHub, scrolled to the Architecture diagram:**
     https://github.com/theShivansh/CROWN-X#architecture
  4. **CloudWatch Logs Insights** in ap-south-1, with both log groups `/aws/lambda/crownx-api` and
     `/aws/lambda/crownx-ingest` selected, and this query pasted, ready to run:
     ```text
     fields @timestamp, message, status_code, error_code, route_key, stage_ms
     | filter @message like "PASTE_REQUEST_ID"
     | sort @timestamp asc
     ```
  5. **BENCHMARKS on GitHub, at "M3 contradictions":**
     https://github.com/theShivansh/CROWN-X/blob/main/docs/BENCHMARKS.md
- **Don't rehearse in workspace A.** Each workspace gets 60 questions an hour, and rehearsal runs also
  change the workflow card's counts. Rehearse in the spare workspace from the pre-flight.
- **Leave 30 seconds between questions,** so Groq doesn't rate-limit you on camera.

## Script
| Time | On screen (do) | Say |
|---|---|---|
| 0:00-0:15 | Tab 1. Point the cursor at `project-brief-v1.pdf` and `organiser-update-3.txt` in the left rail. | "Project facts change across versions. Our brief says submissions close on the 20th, and the organiser's email moved it to the 22nd. A document chatbot answers from whichever passage it finds, and never tells you the sources disagree." |
| 0:15-0:30 | Point at the header: "6 documents indexed", "6 conflicts found". | "CROWN-X is for student and project teams. You upload the versions, ask a question, and every answer cites its passages and shows where the sources disagree." |
| 0:30-0:50 | Press **Ctrl+K**, type **What is the current submission deadline?**, press Enter. While it's "Comparing 3 sources", point at the beam on the conflict card in the Evidence panel. | "Retrieval runs first: keyword and vector search in OpenSearch, filtered to this workspace. The evidence arrives in rank order. Code has already found that two sources disagree, before the model writes a word." |
| 0:50-1:10 | The answer settles. Point at "Sources disagree", both values, and "Current value shown: 22 Sep 2026, rule: newest source date". Click a citation chip **[1]**; the passage highlights on the right. | "The answer says the sources disagree, which value is current, and the rule that chose it. Every sentence cites a passage. Click a citation and there's the exact text." |
| 1:10-1:30 | Scroll to the conflict inspector: brief v1 on the left, organiser update 3 on the right, marked "Newer · 10 Sep". Open **Why was this flagged?** | "The conflict inspector shows both sources side by side. The decision is deterministic code: same fact, same type, different documents, different normalized values. A model never decides that two values conflict." |
| 1:30-1:45 | Click **Open the full timeline**. Point at 20 Sep → 22 Sep with the dashed conflict segment, then the current value. | "The timeline shows how the deadline changed across every source, with the conflict marked." |
| 1:45-2:00 | In the left rail, point at the **Workflows** card "Answer Review Workflow": 6 steps, "3 times". Open **Why detected?**, then **See the events behind it**, then press Esc. | "CROWN-X also notices routines. My team ran this check three times, so it suggests saving it as a workflow. Code counted the steps. The model only named it, and nothing runs automatically." |
| 2:00-2:30 | Tab 3: the architecture diagram. Point along it. | "It's all on AWS, in Mumbai: Amplify hosts the app. API Gateway throttles each route. Two Lambdas, the API and the ingestion worker, each have their own IAM role, and the embedding model runs inside the Lambda. Uploads go straight to S3 on a size-limited link. OpenSearch does hybrid search, and DynamoDB holds the claims, the audit trail and the hourly quotas. Answers come from gpt-oss on Groq, with the key in SSM Parameter Store." |
| 2:30-2:45 | Tab 2: "Workspace not found", with its request ID. Copy the ID. Tab 4: paste it and run the query; the lines appear. | "Every error shows a request ID, and every log line carries it, so a failure on camera takes about five seconds to find in CloudWatch." |
| 2:45-2:55 | Tab 5: point at contradiction precision 1.0 and recall 1.0, measured offline and live. | "Cost stays bounded: one model call per question, none without evidence, and limits counted before any work. What I learned: check model access with a real call on day one, because Bedrock was blocked on my new account. And a log line in a test isn't a log line in CloudWatch." |
| 2:55-3:00 | Back to tab 1, on the conflict inspector. | "See the conflict, the sources, and the reason, in one place." |

## Pre-flight (I run it right before you record)
- [ ] `/health` reports production, Groq and ONNX.
- [ ] Workspace A has 6 documents ready, and the golden question returns `conflict` with the rule
      "newest source date".
- [ ] No console errors on the page. Reduced motion is off in the OS, so the beam and the entrance
      show.
- [ ] Workspace A's workflow card shows the routine with its name.
- [ ] Tab 2 shows a request ID, and Logs Insights finds it.
- [ ] Workspace A has used fewer than 10 of this hour's 60 questions.

## After recording
Share the file or the unlisted YouTube link. I'll check it against the five criteria:
- **idea:** the problem is stated in the first 15 seconds;
- **built on AWS:** the services are named, and CloudWatch is shown live;
- **learning:** said out loud;
- **execution:** the golden path runs without a cut;
- **demo:** 3:00 or less, and every feature the writeup claims appears on screen.

Then I'll list any retakes.
