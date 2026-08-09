# API Specification

This documents the actual implementation of `POST /api/interview`, which
follows `data/technical_spec.md` exactly. No authentication is required.
Interactive Swagger UI is available at `/docs` when the server is running.

## Endpoint

```
POST /api/interview
Content-Type: application/json
```

## Request Body

| Field | Type | Required | Notes |
|---|---|---|---|
| `sessionId` | `string` | always | Stable identifier for this interview session. |
| `candidate` | `object` | only on the **first** request for a session | The candidate profile (see `candidates.json` schema below). |
| `message` | `string` | on every request **after** the first | The candidate's latest response to the previous question. |

Exactly one of `candidate` or `message` should be present on any given
request (the server also tolerates a request with neither `sessionId` nor
the other fields by returning a `422`).

### Candidate object shape

```json
{
  "member": {
    "id": "CAND-009",
    "name": "Zara Ahmadi",
    "jobRole": "AI Engineer",
    "yearsExperience": 1,
    "education": "BS Computer Science",
    "status": "COMPLETED"
  },
  "missions": [
    { "day": 7, "title": "Embeddings Explained", "passed": true, "attempts": 1 },
    { "day": 8, "title": "Vector Databases Overview", "passed": true, "attempts": 1 }
  ],
  "signals": { "commitDays": 31, "missionsCompleted": 31, "missionsFirstTry": 29 }
}
```

`missions[].passed` may be `true`, `false`, or omitted with `"skipped": true`.
`attempts` is the number of tries it took the candidate to pass.

## Responses

### 1. Start interview

**Request**
```json
{ "sessionId": "abc-123", "candidate": { "...": "..." } }
```

**Response** — `200 OK`
```json
{ "reply": "Welcome. Let's begin your interview.", "done": false }
```

### 2. Conversation turn

**Request**
```json
{ "sessionId": "abc-123", "message": "My answer to the previous question..." }
```

**Response** — `200 OK`
```json
{ "reply": "A follow-up or next question.", "done": false }
```

### 3. Interview complete

**Response** — `200 OK`
```json
{
  "reply": "Interview completed.",
  "done": true,
  "feedback": {
    "summary": "3-5 sentence evidence-based overall assessment.",
    "strengths": ["Specific, evidence-based strength", "..."],
    "gaps": ["Specific, evidence-based gap", "..."],
    "next": ["Concrete, actionable next step", "..."]
  }
}
```

## Response Schema

| Field | Type | Present when |
|---|---|---|
| `reply` | `string` | always |
| `done` | `boolean` | always |
| `feedback` | `object \| null` | only when `done == true` |
| `feedback.summary` | `string` | — |
| `feedback.strengths` | `string[]` | — |
| `feedback.gaps` | `string[]` | — |
| `feedback.next` | `string[]` | — |

## Errors

| Status | Cause |
|---|---|
| `422` | Missing `sessionId`, or a request with neither `candidate` nor `message`. |

## Other Endpoints

| Method & Path | Purpose |
|---|---|
| `GET /health` | Liveness check, returns `{"status": "ok"}`. |
| `GET /docs` | Interactive Swagger UI. |
| `GET /openapi.json` | Raw OpenAPI schema. |

## Notes

- The interview is fully driven by `sessionId` — no auth, no cookies.
  Callers must persist and resend the same `sessionId` for every turn of a
  given interview.
- Calling with `candidate` again for a session that's already in progress
  is idempotent: it returns the current in-flight question rather than
  restarting the interview.
- Once an interview is `done`, any further request with that `sessionId`
  returns a polite "already concluded" reply with `done: true` and no
  `feedback` (feedback is only ever returned on the turn that concludes
  the interview).
