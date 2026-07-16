---
name: status
description: Report which of Daimon's abilities are live right now and what he can do, in plain language.
version: 1.0.0
metadata:
  hermes:
    tags: [status, health, capabilities]
    category: ops
---
# Status

Use this when the user asks what you can do, whether something is working, or types
/status.

Check each ability by probing its endpoint from the shell (short timeout), then report in
human terms — never name the underlying services, ports, or tech.

```
curl -fsS --max-time 3 http://ollama:11434/api/tags        # thinking + vision
curl -fsS --max-time 3 http://daimon-searxng:8080/healthz  # web search
curl -fsS --max-time 3 http://daimon-tts:8880/health       # voice replies
curl -fsS --max-time 3 http://qdrant:6333/readyz           # memory / knowledge
curl -fsS --max-time 3 http://grafana:3000/api/health      # dashboards
```

Map each result to an ability and say whether it's up:

- thinking + vision → "I can think and see images"
- web search → "I can search the web"
- voice replies → "I can answer out loud"
- memory / knowledge → "I can remember and recall what you save"
- dashboards → "I'm being monitored"

Lead with a one-line verdict ("Everything's up." or "Voice is down right now"), then a short
list. If something is down, say plainly what's affected and that the user can bring it back.
Keep it warm and brief — this is a quick check-in, not a report.
