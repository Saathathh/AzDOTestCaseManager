"""ASGI entrypoint shim so `uvicorn main:app` works from project root."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"

# Ensure backend-local absolute imports (e.g., `from services...`) resolve.
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from backend.main import app
