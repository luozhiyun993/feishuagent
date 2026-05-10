# Feishu AI Event Planner — Design Spec

## Overview

A Feishu Bot that helps users plan events through multi-turn conversation. The bot uses DeepSeek LLM for natural language understanding and generates Feishu interactive cards as event invitations.

## Architecture

```
User(Feishu) <--> Feishu WebSocket <--> Bot Service <--> DeepSeek API
                                |
                         Feishu Open API (send messages/cards)
```

### Files

| File | Responsibility |
|------|---------------|
| `main.py` | Entry point, WebSocket connection, event loop |
| `feishu_client.py` | Feishu SDK: get token, send messages, send cards |
| `deepseek_client.py` | DeepSeek API wrapper, conversation history management |
| `conversation.py` | Conversation state machine, multi-turn dialog flow, activity info extraction |

## Conversation Flow

States: `IDLE → INTRO → ASK_TYPE → ASK_PEOPLE → ASK_TIME → ASK_LOCATION → CONFIRM → DONE`

- **New conversation**: Any message when state is `IDLE` enters `INTRO`
- **After DONE**: Next user message resets to `IDLE`, starts fresh conversation
- **Reset keywords**: "重新开始", "算了", "新活动" clear session to `IDLE`

## Card Format

```
Title: 活动邀请
Body: Activity name, time, location, organizer
```

## Session Management

In-memory dict keyed by `chat_id`. No persistence needed for MVP.

## Dependencies

- `openai>=1.0.0` — DeepSeek API (OpenAI compatible)
- `websocket-client` — Feishu WebSocket
- `httpx` — HTTP client for Feishu Open API
- `python-dotenv` — env vars management

## API Details

### DeepSeek
- Base URL: `https://api.deepseek.com`
- Endpoint: `/v1/chat/completions`
- Model: `deepseek-v4-flash`
- Auth: Bearer token via `DEEPSEEK_API_KEY`

### Feishu
- Auth: App ID + App Secret → tenant access token
- WebSocket: `wss://open.feishu.cn/open-apis/event/v1`
- Send message: `POST https://open.feishu.cn/open-apis/im/v1/messages`
- Send card: `msg_type: interactive` with card JSON
