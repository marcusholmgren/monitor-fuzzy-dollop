from fastapi import FastAPI

app = FastAPI(
    title="monitor-fuzzy-dollop",
    description="Experimental API for collecting IoT readings",
    version="0.1.0",
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


def main() -> None:
    print("Hello from monitor-fuzzy-dollop!")


__all__ = ["app", "main"]
