from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="howedo-cockpit",
        description="Run the HOWEDO API and operator cockpit.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    return parser


def main() -> None:
    args = build_parser().parse_args()

    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit(
            "The cockpit requires the API profile. "
            "Install it with: pip install 'howedo-continuity[api]'"
        ) from exc

    uvicorn.run(
        "howedo.api.app:app",
        host=args.host,
        port=args.port,
        access_log=False,
    )


if __name__ == "__main__":
    main()
