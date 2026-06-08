from __future__ import annotations

try:
    from .ingest_311 import main as ingest_311
    from .ingest_permits import main as ingest_permits
except ImportError:
    from ingest_311 import main as ingest_311
    from ingest_permits import main as ingest_permits


def main() -> None:
    ingest_311()
    ingest_permits()


if __name__ == "__main__":
    main()
