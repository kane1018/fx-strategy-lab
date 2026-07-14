"""Launch the local-only H-11 manual signal UI on loopback."""

from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Start local H-11 signal UI")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    uvicorn.run(
        "app.main_h11_manual:app",
        host="127.0.0.1",
        port=args.port,
        reload=False,
        access_log=False,
    )


if __name__ == "__main__":
    main()
