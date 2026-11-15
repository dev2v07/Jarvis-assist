# Jarvis App Server

Jarvis exposes a local JSON-RPC 2.0 app-server boundary while keeping the
existing agent pipeline as the execution engine.

## Transports

- `POST /app-server/rpc` — one JSON-RPC request/response;
- `WebSocket /app-server/ws` — bidirectional requests plus `event`
  notifications;
- `GET /runtime/events` — compatibility polling endpoint.

## Methods

- `initialize`
- `thread/start` / `thread/create`
- `thread/list`
- `thread/read` / `thread/resume`
- `turn/start`
- `turn/interrupt` / `turn/abort`
- `runtime/events`

## Turn order

```text
thread.started|thread.resumed
  -> turn.started
  -> item.started (planner)
  -> item.completed (planner)
  -> task.started (executor)
  -> item.started/completed (specialist agent)
  -> item.started/completed (critic)
  -> item.completed (assistant_message)
  -> turn.completed
```

`chat_id` is the persistent Jarvis thread identity. `request_id` identifies
the inbound message. `turn_id` identifies one execution cycle and is carried
through Planner, Executor, specialist agents and Critic.

The implementation is intentionally an adapter rather than a replacement for
the existing MessageBus. It provides the Codex-style lifecycle and transport
contract first; persistent event history, streaming deltas and a durable task
queue remain separate follow-up work.
