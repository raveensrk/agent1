"""jsonschema validation for config.json and prices.json.

Bad config currently crashes deep in the pipeline or silently ignores keys.
These schemas fail fast at load time with a readable message.
"""

from __future__ import annotations

CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "output_dir": {"type": "string", "minLength": 1},
        "home": {"type": "string", "minLength": 1},
        "aa_api_key": {"type": "string", "minLength": 1},
        "openrouter_api_key": {"type": "string", "minLength": 1},
        "extra_harnesses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "label": {"type": "string"},
                    "glob": {"type": "string", "minLength": 1},
                },
                "required": ["name", "glob"],
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}

PRICE_RATES = {
    "type": "object",
    "properties": {
        "input": {"type": "number", "minimum": 0},
        "output": {"type": "number", "minimum": 0},
        "cache_read": {"type": "number", "minimum": 0},
        "cache_write": {"type": "number", "minimum": 0},
    },
    "additionalProperties": False,
}

PRICES_SCHEMA = {
    "type": "object",
    "propertyNames": {"pattern": "^[^/]+(/[^/]+)?$"},
    "additionalProperties": PRICE_RATES,
}


def _validate(data, schema, label):
    """Raise SystemExit with a readable message, or return data unchanged."""
    try:
        import jsonschema
    except ImportError:
        return data  # schema checking is best effort without the dependency
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as exc:
        where = ".".join(str(p) for p in exc.absolute_path) or "(root)"
        raise SystemExit("ERROR: invalid %s at %s: %s" % (label, where, exc.message))
    return data


def validate_config(data):
    return _validate(data, CONFIG_SCHEMA, "config.json")


def validate_prices(data):
    return _validate(data, PRICES_SCHEMA, "prices.json")
