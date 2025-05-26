import os


def load_dotenv(path: str | None = None) -> None:
    """Simple dotenv loader for tests."""
    if path is None:
        path = ".env"
    try:
        with open(path) as f:
            for line in f:
                if not line.strip() or line.strip().startswith('#'):
                    continue
                key, _, value = line.strip().partition('=')
                os.environ.setdefault(key, value)
    except FileNotFoundError:
        pass
