from app.db import SessionLocal, ensure_schema
from app.services.settings_store import ensure_settings


def main() -> None:
    ensure_schema()
    with SessionLocal() as session:
        ensure_settings(session)
    print("SQLite database initialized.")


if __name__ == "__main__":
    main()
