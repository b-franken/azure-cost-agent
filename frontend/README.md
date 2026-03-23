# CopilotKit Frontend (Experimental)

CopilotKit + AG-UI frontend for the Azure Cost Agent.

## Status: Not production-ready

This frontend has known incompatibilities with the HandoffBuilder workflow pattern:

1. **Multi-turn fails**: The AG-UI workflow runner emits `interrupt` events in `RUN_FINISHED` that CopilotKit cannot resume correctly. The second question in a conversation does not receive a response.

2. **TOOL_CALL mismatch**: HandoffBuilder internal tool calls (`handoff_to_*`) emit `TOOL_CALL_START` without matching `TOOL_CALL_END`, causing CopilotKit to error with "Cannot send RUN_FINISHED while tool calls are still active."

3. **Input splitting**: Under certain conditions, CopilotKit sends each character as a separate message instead of the full input.

These are framework-level incompatibilities between `agent-framework-ag-ui` (RC5, March 2026) and CopilotKit. They may be resolved in future releases of either framework.

## Use instead

Use the Chainlit frontend (`frontend-chainlit/`) which communicates directly with the Python workflow API and works correctly for multi-turn conversations.

## If you want to try it anyway

tried everything i know but if someone knows how to fix would be awesome <3

```bash
# Terminal 1: AG-UI backend
make api

# Terminal 2: CopilotKit frontend
make frontend
```

The AG-UI SSE endpoint works correctly when called directly:

```bash
curl -N -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"messages":[{"role":"user","content":"show tag coverage"}]}'
```
