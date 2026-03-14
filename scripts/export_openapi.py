"""Export the FastAPI OpenAPI spec to a JSON file for Sphinx documentation."""

import json
import os

from api.main import create_app


def main():
    app = create_app()
    spec = app.openapi()

    output_path = os.path.join(os.path.dirname(__file__), '..', 'docs', 'api-docs', 'openapi.json')
    output_path = os.path.abspath(output_path)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(spec, f, indent=2)

    print(f"OpenAPI spec exported to {output_path}")


if __name__ == '__main__':
    main()
