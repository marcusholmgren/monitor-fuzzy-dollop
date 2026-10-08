# monitor-fuzzy-dollop
Experimental API for collecting IoT readings


## How to Run

1. Start the stack in the background:
```bash
  docker compose up -d --build
```

2. Verify services and health check:
```bash
  docker compose ps
  curl http://localhost:8000/health
```

3. Stop the stack:
```bash
  docker compose down
```

## Test

  Run pytest:
```bash
  uv run pytest -v
```
