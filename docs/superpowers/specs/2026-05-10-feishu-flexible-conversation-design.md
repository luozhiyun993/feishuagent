# Feishu Flexible Conversation Flow Design

## Goal

Replace the fixed-step conversation state machine with a slot-driven flow that lets users provide event information in any order. The bot should extract available fields from each message, ask only for missing information, confirm once all required fields are present, and generate the final invitation card after confirmation.

## Required Slots

- `activity_type`
- `people`
- `time`
- `location`

These four fields remain the minimum information required before card generation.

## Conversation Model

Each incoming user message is processed in two stages:

1. Extract structured slot updates from the user message.
2. Generate a natural-language reply based on the merged slot state and any missing fields.

The backend owns slot state. The model can suggest extracted values, but it does not own session transitions directly.

## Extraction Step

Add a structured extraction helper in `conversation.py` that asks the model to return JSON with this shape:

```json
{
  "activity_type": "",
  "people": "",
  "time": "",
  "location": "",
  "is_confirmation": false
}
```

Rules:

- Missing fields return empty strings.
- Only update slots when the model extracts a concrete value.
- `is_confirmation` is true only when the user is explicitly confirming completed details.
- If JSON parsing fails, fall back to empty extraction and continue safely.

## Session State

Keep lightweight session state, but simplify it:

- `IDLE`: no active collected plan yet
- `COLLECTING`: gathering slots in any order
- `CONFIRM`: all required slots are present and awaiting explicit confirmation
- `DONE`: card already generated for the current plan

The old per-question states (`ASK_TYPE`, `ASK_PEOPLE`, `ASK_TIME`, `ASK_LOCATION`) are removed.

## Reply Generation

After merging extracted slots:

- If not all required slots are present:
  - ask about only the missing fields
  - if multiple fields are missing, ask naturally and concisely, preferably focusing on one or two at a time
- If all required slots are present and session is not yet confirmed:
  - summarize the full plan and ask the user to confirm
- If user confirms while all slots are present:
  - generate the card and send a short completion reply
- If user sends new slot information while in `CONFIRM`:
  - update the relevant slots and regenerate the confirmation summary instead of resetting the whole session
- If user sends a new request after `DONE`:
  - reset and begin a fresh planning session

## Logging

Keep the existing inbound/outbound logs and add slot-level diagnostics:

- `User: ...`
- `Extracted slots: {...}`
- `Session slots: {...}`
- `Bot reply: ...`

This should make it clear whether failures happen during event receipt, slot extraction, reply generation, or Feishu message sending.

## Error Handling

- Model extraction failure should not crash the flow.
- Invalid or partial extraction should keep the current session and ask a clarifying follow-up.
- Message send failures remain logged in `main.py`.

## Testing

Add unit tests for:

- user provides all slots out of order across multiple messages
- user provides multiple slots in one message
- user confirms after all slots are present and receives a card
- user modifies details during confirmation and the session updates instead of resetting
- extraction failure falls back safely without crashing

## Scope

This change is limited to `conversation.py`, `test_conversation.py`, and logging already emitted from `main.py`. No Feishu SDK integration changes are required.
