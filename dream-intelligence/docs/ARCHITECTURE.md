# Day 1 boundaries

Presentation (React Today + Intelligence Card)
↓
API (FastAPI /api/v1)
↓
Intelligence Core (typed intelligence contract; mock analysis only)
↓
Infrastructure (SQLAlchemy + SQLite)

Future Dream Stream integration uses the DSIH API. Dream Stream must not access the DSIH database directly.

Only sources, items and analysis exist. Seed data supplies all scores; there is no real intelligence or scoring engine. The Today bootstrap endpoint lists all locally seeded analyzed records, without a date filter. Stats use stored values: important = priority >= 80; relevant = Dream Stream relevance >= 80; must_read = priority >= 90 and action READ. These are display counts, not a scoring engine.

SQLite is local; startup creates the tables without seeding; mock seed is an explicit command. NewsNowConnector normalizes three fixed public sources into raw items. Raw items have no analysis and do not appear in Today. No LLM, scheduling or deployment.


DSIH-004 adds an injectable LLMClient protocol, an OpenAI-compatible HTTP client, Pydantic analysis validation and a pure versioned priority function. Manual analyzer commands write only analysis; raw items remain immutable. Production commands require explicit provider configuration. Fake clients exist only in tests. No framework, scheduler or new database table is introduced. Today integration is unchanged and outside this task.
