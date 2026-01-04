# Agent-Skills KB & Learning Loop Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SKILL EXECUTION FLOW                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │ schema-infer │───▶│code-implement│───▶│ code-validate│                   │
│  │   (HYBRID)   │    │(ADVISOR_ONLY)│    │(DETERMINISTIC)                   │
│  └──────────────┘    └──────────────┘    └───────┬──────┘                   │
│         │                   │                    │                          │
│         │                   │              ┌─────▼─────┐                    │
│         ▼                   ▼              │  errors?  │                    │
│    ┌─────────┐        ┌─────────┐         └─────┬─────┘                    │
│    │ KB READ │        │ KB READ │               │                          │
│    │patterns │        │patterns │         yes   │   no                     │
│    └─────────┘        └─────────┘          ┌────┴────┐                     │
│                             │              ▼         ▼                      │
│                             │         ┌────────┐  ┌────────┐               │
│                             │         │code-fix│  │EMIT    │               │
│                             │         │(max 3) │  │GOLDEN  │               │
│                             │         └────┬───┘  └────────┘               │
│                             │              │                                │
│                             │         ┌────▼────┐                          │
│                             │         │fixed?   │                          │
│                             │         └────┬────┘                          │
│                             │         yes  │  no (after 3)                 │
│                             │         ┌────┴────┐                          │
│                             │         ▼         ▼                          │
│                             │    ┌────────┐ ┌──────────┐                   │
│                             │    │EMIT    │ │ESCALATE  │                   │
│                             │    │PROMO   │ │to human  │                   │
│                             │    │CAND    │ └──────────┘                   │
│                             │    └────────┘                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

## KB Data Flow

```
                    KNOWLEDGE BASE (Read-Only at Runtime)
┌─────────────────────────────────────────────────────────────────────┐
│  runtime/kb/patterns/                                                │
│  ├── auth_patterns.json      (5 patterns: BaseCredential, OAuth2...)│
│  ├── node_patterns.json      (8 patterns: BaseNode, execute()...)   │
│  ├── pagination_patterns.json(4 patterns: cursor, offset, link...)  │
│  └── ts_python_idioms.json   (7 patterns: async→sync, ?.→.get()...) │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                        ┌──────────▼──────────┐
                        │  KnowledgeBase      │
                        │  .load_all()        │
                        │  .get_by_category() │
                        │  .get_by_id()       │
                        └──────────┬──────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         │                         │                         │
         ▼                         ▼                         ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  schema-infer   │    │ code-implement  │    │   code-fix      │
│                 │    │                 │    │                 │
│ inputs:         │    │ inputs:         │    │ inputs:         │
│  _kb_patterns   │    │  _kb_patterns   │    │  _kb_patterns   │
│  (ts_to_python) │    │  (auth, ts_py,  │    │  (ts_to_python, │
│                 │    │   pagination)   │    │   service_quirk)│
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Category Normalization

```
   INPUT CATEGORIES              CANONICAL CATEGORIES
   (from old patterns)           (schema.json truth)
   
   "authentication"  ──────┐
                           ├────▶  "auth"
   "auth"  ────────────────┘
   
   "type_conversion" ──────┐
   "async_to_sync"   ──────┼────▶  "ts_to_python"
   "idiom_conversion"──────┤
   "ts_to_python"    ──────┘
   
   "pagination"      ─────────────▶  "pagination"
   
   "service_quirk"   ─────────────▶  "service_quirk"
```

## Learning Loop Emission

```
┌─────────────────────────────────────────────────────────────────────┐
│                     EXECUTOR.execute()                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. Run skill                                                        │
│  2. Validate outputs                                                 │
│  3. Check post-gates                                                 │
│  4. IF terminal AND success:                                         │
│     │                                                                │
│     ├─── skill == "code-implement" OR "code-convert"                │
│     │         │                                                      │
│     │         ▼                                                      │
│     │    ┌─────────────────────────────────────────┐                │
│     │    │  _emit_golden_artifact()                │                │
│     │    │  - Extract generated_code from outputs  │                │
│     │    │  - Load schema, trace_map from artifacts│                │
│     │    │  - Package as GoldenArtifactPackage     │                │
│     │    │  - Write to artifacts/golden/<id>/      │                │
│     │    └─────────────────────────────────────────┘                │
│     │                                                                │
│     └─── skill == "code-fix" AND fix_state exists                   │
│                 │                                                    │
│                 ▼                                                    │
│            ┌─────────────────────────────────────────┐              │
│            │  _emit_promotion_candidate()            │              │
│            │  - Get error_message, original_code     │              │
│            │  - Get fixed_code from outputs          │              │
│            │  - Categorize error → suggest KB cat    │              │
│            │  - Write to artifacts/promotion_cand/   │              │
│            └─────────────────────────────────────────┘              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Promotion Pipeline (Human-in-the-Loop)

```
   RUNTIME (Automatic)                    HUMAN REVIEW (Manual)
   
   ┌──────────────┐                      ┌──────────────────────┐
   │ code-implement│                      │ scripts/             │
   │ SUCCESS      │                      │ promote_artifact.py  │
   └──────┬───────┘                      └──────────┬───────────┘
          │                                         │
          ▼                                         │
   ┌──────────────┐     list golden                 │
   │artifacts/    │◀────────────────────────────────┤
   │golden/<id>/  │                                 │
   │ manifest.json│     promote golden <id>         │
   │ code/        │────────────────────────────────▶│
   │ schema.json  │         --category auth         │
   └──────────────┘                                 │
                                                    │
   ┌──────────────┐                                 │
   │ code-fix     │                                 │
   │ SUCCESS      │                                 │
   └──────┬───────┘                                 │
          │                                         │
          ▼                                         │
   ┌──────────────┐     list candidates             │
   │artifacts/    │◀────────────────────────────────┤
   │promotion_    │                                 │
   │candidates/   │     promote candidate <file>    │
   │ <id>.json    │────────────────────────────────▶│
   └──────────────┘                                 │
                                                    ▼
                                           ┌───────────────┐
                                           │ runtime/kb/   │
                                           │ patterns/     │
                                           │ <cat>.json    │
                                           │ (NEW PATTERN) │
                                           └───────────────┘
```

## Key Files

| File | Purpose |
|------|---------|
| `runtime/kb/loader.py` | Load/validate patterns, category normalization |
| `runtime/kb/__init__.py` | Exports: `KnowledgeBase`, `CANONICAL_CATEGORIES` |
| `runtime/executor.py` | KB injection, learning loop emission |
| `runtime/learning_loop.py` | `GoldenArtifactPackage`, `PromotionCandidate`, `LearningLoopEmitter` |
| `scripts/promote_artifact.py` | CLI for human review + promotion |

## Commands Reference

### Validation
```bash
python3 -m pytest -q                              # All tests
python3 scripts/validate_skill_contracts.py       # 12 skill contracts
python3 scripts/validate_trace_map.py <file>      # Trace evidence
python3 scripts/validate_sync_celery_compat.py .  # Async detection
```

### Gates (Pre-PR)
```bash
python3 scripts/agent_gate.py --correlation-id <id>
python3 scripts/agent_gate.py --correlation-id <id> --skip-pytest
```

### KB Promotion
```bash
python3 scripts/promote_artifact.py list golden
python3 scripts/promote_artifact.py list candidates
python3 scripts/promote_artifact.py golden <id> --category auth
python3 scripts/promote_artifact.py candidate <file> --category ts_to_python
```
