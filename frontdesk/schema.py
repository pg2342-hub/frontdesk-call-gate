"""The one record every call must end in."""

DEPARTMENTS = ["housekeeping", "engineering", "front_desk"]

RECORD_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string", "description": "What the agent says to the guest."},
        "task": {
            "anyOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "properties": {
                        "department": {"type": "string", "enum": DEPARTMENTS},
                        "room": {
                            "anyOf": [{"type": "string"}, {"type": "null"}],
                            "description": "Room number, or null if not known for sure.",
                        },
                        "request": {"type": "string"},
                        "priority": {"type": "string", "enum": ["normal", "urgent"]},
                    },
                    "required": ["department", "room", "request", "priority"],
                    "additionalProperties": False,
                },
            ]
        },
        "handoff": {
            "type": "object",
            "properties": {
                "now": {"type": "boolean"},
                "reason": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            },
            "required": ["now", "reason"],
            "additionalProperties": False,
        },
        "lead": {
            "anyOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": ["group", "event"]},
                        "dates": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                        "rooms": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                        "people": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                        "name": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                        "callback": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                        "notes": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    },
                    "required": ["type", "dates", "rooms", "people", "name", "callback", "notes"],
                    "additionalProperties": False,
                },
            ]
        },
        "review_flag": {"type": "boolean", "description": "True only when acting on a request it is unsure about."},
    },
    "required": ["reply", "task", "handoff", "lead", "review_flag"],
    "additionalProperties": False,
}
