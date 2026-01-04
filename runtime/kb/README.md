# Knowledge Base (KB) for Agent-Skills

This directory contains curated, versioned, human-reviewable knowledge entries that help the agent make better decisions. The KB is **read-only at runtime** — agents may propose changes as artifacts, but changes must be made via PR.

## Structure

```
runtime/kb/
├── README.md                       # This file
├── schema.json                     # JSON Schema for KB entries
├── loader.py                       # Python loader with validation
└── patterns/
    ├── auth_patterns.json          # Credential and authentication patterns
    ├── node_patterns.json          # Node implementation patterns
    ├── pagination_patterns.json    # Pagination patterns
    └── ts_python_idioms.json       # TypeScript → Python conversion patterns
```

## Pattern Categories

### Auth Patterns (`auth_patterns.json`)
Patterns for implementing credentials:
- **BaseCredential Structure** (`auth-001`): Base class with properties array pattern
- **OAuth2 Stateless Token Refresh** (`auth-002`): Token refresh returning new data
- **Service-Specific OAuth2** (`auth-003`): Extending OAuth2 for specific services (e.g., Slack)
- **API Key Credential** (`auth-004`): Simple API key authentication
- **Database Connection** (`auth-005`): Connection string building pattern

### Node Patterns (`node_patterns.json`)
Patterns for implementing nodes:
- **BaseNode Structure** (`node-001`): Node class with type, version, description, properties
- **Resource-Operation Pattern** (`node-002`): Multi-resource nodes with display_options
- **Execute Method** (`node-003`): Sync execute() implementation
- **Trigger Method** (`node-004`): Webhook/polling trigger implementation
- **Expression Evaluation** (`node-005`): Resolving `{{$json.field}}` patterns
- **Credential Retrieval** (`node-006`): Fetching and decrypting credentials
- **Parameter Types** (`node-007`): NodeParameterType enum mapping
- **HTTP Requests** (`node-008`): Sync HTTP with timeout (Celery-safe)

### Pagination Patterns (`pagination_patterns.json`)
- **Cursor-Based** (`page-001`): Using next_cursor tokens
- **Offset-Limit** (`page-002`): Traditional pagination
- **Link Header** (`page-003`): RFC 5988 pagination
- **Return All Pattern** (`page-004`): Node returnAll/limit toggle

### TypeScript to Python Idioms (`ts_python_idioms.json`)
- **Interface to Pydantic** (`ts-py-001`): TypeScript interface → Pydantic BaseModel
- **Async to Sync** (`ts-py-002`): async/await → sync (Celery-safe)
- **Enum Conversion** (`ts-py-003`): TypeScript enum → Python str Enum
- **Expression Evaluation** (`ts-py-004`): n8n expressions → Python
- **Optional Chaining** (`ts-py-005`): `?.` → `.get()` chains
- **Display Options** (`ts-py-006`): displayOptions → display_options dict
- **Array Methods** (`ts-py-007`): Array methods → list comprehensions

## Entry Format

Each pattern is a JSON entry with this structure:

```json
{
  "id": "unique-pattern-id",
  "version": "1.0.0",
  "category": "auth | pagination | ts_to_python | service_quirk",
  "name": "Human-readable name",
  "description": "What this pattern covers",
  "applicability": {
    "services": ["slack", "github"],
    "node_types": ["credential", "regular", "trigger"]
  },
  "pattern": {
    "type": "auth | pagination | ts_to_python | service_quirk",
    /* Category-specific fields - see schema.json */
  },
  "examples": [
    {
      "input": "Example input or context",
      "output": "Example output or implementation",
      "notes": "Additional notes"
    }
  ],
  "promoted_from": "correlation-id",
  "created_at": "2024-01-01T00:00:00Z"
}
```

## Usage

```python
from runtime.kb import KnowledgeBase

kb = KnowledgeBase()

# Load all patterns
all_patterns = kb.load_all()

# Get patterns by category
auth_patterns = kb.get_by_category("auth")
node_patterns = kb.get_by_category("ts_to_python")

# Get pattern by ID
oauth_pattern = kb.get_by_id("auth-002")

# List all categories
categories = kb.get_categories()

# Check if pattern exists
if kb.has_pattern("node-001"):
    pattern = kb.get_by_id("node-001")
```

## Key Principles

### Sync Celery Compatibility
All code patterns must be sync (no async/await) with explicit timeouts:
```python
# ✓ Correct
response = requests.get(url, timeout=30)

# ✗ Wrong - no timeout
response = requests.get(url)

# ✗ Wrong - async
response = await aiohttp.get(url)
```

### Expression Resolution
n8n expressions like `{{$json.field}}` must be resolved by ExpressionEngine:
```python
value = self.get_node_parameter('chatId', parameters, item)
# Internally resolves {{$json.chat_id}} from item
```

### Resource-Operation Pattern
Multi-resource nodes follow this structure:
```python
NodeParameter(name='resource', type=OPTIONS, options=[...])
NodeParameter(name='operation', type=OPTIONS, display_options={'show': {'resource': ['message']}})
NodeParameter(name='channel', display_options={'show': {'resource': ['message'], 'operation': ['post']}})
```

## Promotion Pipeline

Patterns are added to the KB via the promotion pipeline:

1. **Agent generates**: After successful `code-implement` or `code-convert`, agent emits golden artifact
2. **Fix loop learns**: After successful `code-fix` resolution, agent emits promotion candidate  
3. **Human reviews**: Candidate is reviewed via `scripts/promote_artifact.py`
4. **Promotion**: If accepted, candidate is converted to KB entry

### Promotion Commands

```bash
# List golden artifacts ready for promotion
python3 scripts/promote_artifact.py list golden

# List promotion candidates (from fix-loop successes)
python3 scripts/promote_artifact.py list candidates

# Promote a golden artifact to the auth category
python3 scripts/promote_artifact.py golden <correlation-id> --category auth

# Promote a fix candidate (uses suggested category)
python3 scripts/promote_artifact.py candidate artifacts/promotion_candidates/<file>.json

# Dry-run to see what would be promoted
python3 scripts/promote_artifact.py golden <id> --category ts_to_python --dry-run
```

See `runtime/learning_loop.py` for promotion candidate structure.

## KB Maintenance Lane (Mining Pipeline)

The KB Maintenance Lane is a production-safe learning loop that extracts patterns from reference implementations and pipeline artifacts. All mining is **deterministic** and **read-only** — candidates are written to `artifacts/`, not to KB.

### Mining Scripts

Located in `scripts/kb/`:

| Script | Purpose | Source |
|--------|---------|--------|
| `mine_back_nodes.py` | Extract credential, HTTP, pagination patterns | `back/nodes/*.py` |
| `mine_back_credentials.py` | Extract auth patterns | `back/credentials/*.py` |
| `mine_trace_maps.py` | Extract ts_to_python patterns | `artifacts/**/trace_map.json` |
| `mine_fix_candidates.py` | Deduplicate fix candidates | `artifacts/**/fix_candidate*.json` |
| `report_gaps.py` | Coverage gap analysis | `skills/*/SKILL.md` vs KB |

### Running Mining Scripts

```bash
# Mine node patterns from reference implementation
python scripts/kb/mine_back_nodes.py --nodes-dir /path/to/back/nodes -v

# Mine credential patterns
python scripts/kb/mine_back_credentials.py --credentials-dir /path/to/back/credentials -v

# Mine trace maps from all artifacts
python scripts/kb/mine_trace_maps.py --artifacts-dir artifacts/ -v

# Consolidate fix candidates
python scripts/kb/mine_fix_candidates.py --artifacts-dir artifacts/ --min-occurrences 2 -v

# Analyze KB coverage gaps
python scripts/kb/report_gaps.py --skills-dir skills/ --kb-dir runtime/kb/ -v
```

### Mining Output Structure

Each mining run creates:
```
artifacts/<run_id>/
├── manifest.json              # Run metadata
├── summary.md                 # Human-readable report
└── promotion_candidates/      # Candidate JSON files
    ├── cand-abc12345.json
    └── cand-def67890.json
```

### Promoting Mining Candidates

```bash
# List all mining runs
python scripts/promote_artifact.py list mining-runs

# Preview candidates from a run
python scripts/promote_artifact.py mining-run <run_id>

# Promote all candidates from a run (with review)
python scripts/promote_artifact.py mining-run <run_id> --all

# Promote only auth patterns from a run
python scripts/promote_artifact.py mining-run <run_id> --category auth --all

# Dry-run to preview
python scripts/promote_artifact.py mining-run <run_id> --all --dry-run
```

### Mining Candidate Schema

Mining candidates use the schema defined in `runtime/kb/candidates.py`:

```python
@dataclass
class MiningCandidate:
    candidate_id: str           # Unique ID (cand-<hash>)
    candidate_type: CandidateType  # PATTERN or FIX
    category: str               # auth, pagination, ts_to_python, service_quirk
    name: str                   # Human-readable name
    description: str            # What this pattern covers
    pattern_data: dict          # Category-specific data
    source_refs: list[SourceReference]  # Evidence trail
    confidence: str             # high, medium, low
    stats: CandidateStats | None  # For FIX candidates
    mining_run_id: str          # Run that generated this
    timestamp: str              # ISO timestamp
```

### Key Invariants

1. **KB is READ-ONLY**: Mining scripts NEVER write to `runtime/kb/`
2. **Deterministic**: Same input → same candidates (use `sort_keys=True`)
3. **Validated**: All candidates validated before output
4. **Evidence-based**: Each candidate links to source evidence
5. **PR-gated**: All promotions require human review via PR

## Rules

1. **Read-only at runtime**: Agent code MUST NOT write to KB directly
2. **Versioned**: All entries have semantic version
3. **Validated**: All entries validated against schema.json on load
4. **Auditable**: Each entry tracks creation timestamp and promotion source
