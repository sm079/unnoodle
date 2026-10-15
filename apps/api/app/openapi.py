"""Writes the API's OpenAPI schema, which the web app generates its types from: python -m app.openapi openapi.json"""

import json
import sys
from pathlib import Path

from app.main import create_app


def main() -> None:
    target = Path(sys.argv[1])
    schema = create_app().openapi()
    # Fixed line endings and a trailing newline, so the file only changes when the schema does
    target.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
