"""
The published HTTP contract: this service's OpenAPI spec, rendered for `contracts/`.

`make contract` writes it to `contracts/openapi/backend-ot.openapi.json`; the unit test
`tests/unit/test_contract.py` fails while the committed file differs from this output.
The spec's `info.version` (set in `app.create_app`) is the contract version: bump it for a
breaking change (a removed or renamed route, field or enum value).
"""

import json

from fastapi import FastAPI


def render_openapi_contract(app: FastAPI) -> str:
    """Deterministic JSON text: sorted keys, 2-space indent, trailing newline."""
    return json.dumps(app.openapi(), sort_keys=True, indent=2, ensure_ascii=False) + "\n"
