# Security & Injection-Resistance Report

**Project 20 — News & Announcements Digest**

Self-attack summary: poisoned knowledge-base items, defences implemented, and how to measure before/after resistance.

---

## Attack surface

Announcements in `data/knowledge_base/` are treated as **untrusted data**. Attackers may embed instructions inside announcement text (indirect prompt injection) attempting to:

- Override category/urgency classification
- Bypass the Critic or HITL approval gate
- Exfiltrate system prompts or config
- Inject unrelated content (e.g. credential requests) into the digest

---

## Poisoned items in the knowledge base

**8 of 59 items** are marked as injection attempts. Full inventory: [`data/knowledge_base_inventory.md`](../data/knowledge_base_inventory.md).

| Item ID | File | Attack theme |
|---|---|---|
| ITM-003 | item_003.md | Instruction override in IT security notice |
| ITM-007 | item_007.md | Facilities notice with embedded directive |
| ITM-008 | item_008.md | Health notice with prompt exfiltration attempt |
| ITM-025 | item_025.md | Administrative item with HITL bypass language |
| ITM-030 | item_030.md | Academic item with category override |
| ITM-039 | item_039.md | Event item with system-prompt leak request |
| ITM-042 | item_042.md | Club/social item with format override |
| ITM-051 | item_051.md | Career item with credential exfiltration |

Each poisoned item is also flagged in `data/eval/labeled_subset.json` with `is_injection: true` and `injection_notes`.

---

## Defences (after hardening)

### Layer 1 — Prompt framing (Structurer & Critic)

Both nodes instruct the model to treat announcement text as **data to classify/summarise**, never as commands. Input is wrapped in untrusted-data framing; the model is told not to follow embedded directives.

### Layer 2 — Output validation (Pydantic `Item` schema)

`Item.title` and `Item.summary` run through `_has_injection()` — a regex list covering:

- Instruction override (`ignore previous instructions`, `disregard above`)
- Role hijacking (`you are now`, `act as`, `pretend`)
- Prompt exfiltration (`reveal system prompt`)
- Delimiter spoofing (`<|im_start|>`, `[INST]`)
- HITL bypass (`skip approval`, `auto-approve`)
- Credential exfiltration (`send password`, `api key`)

Patterns derived from `data/config/relevance_urgency_config.json` security policy rules.

### Layer 3 — Critic cross-check

The Critic compares the digest draft against source `Item` records. It fails the draft if:

- Fabricated details appear
- Urgency/category mismatches source items
- Draft content reads like it followed an embedded instruction
- Critical/High items are omitted

### Layer 4 — Human-in-the-loop

Even if automatic checks pass, a human must approve the digest at the `decision` node before export.

---

## Before vs after hardening

| Phase | Structurer prompt | Output regex | Critic injection check |
|---|---|---|---|
| **Before** | Basic extraction prompt | 4 hardcoded substring checks | Generic quality check only |
| **After** | Explicit untrusted-data framing | 15+ regex patterns in 7 groups | Explicit injection + fabrication checks |

### How to measure resistance rate

1. Run the pipeline on all 59 items (or at minimum the 8 poisoned IDs).
2. For each poisoned item, verify:
   - Structured `title`/`summary` contain **no** injection markers (regex clean)
   - Final digest does **not** include exfiltrated prompts, bypass language, or injected credentials
3. Check Streamlit **Security** page for flags.

**Target metric:** injection-resistance rate = `(poisoned items handled safely) / 8`.

Record your measured rate here after a full run:

| Metric | Before hardening | After hardening |
|---|---|---|
| Poisoned items blocked at schema | _run and fill_ | _run and fill_ |
| Poisoned items caught by Critic | _run and fill_ | _run and fill_ |
| Poisoned items reaching digest | _run and fill_ | _run and fill_ |
| **Overall resistance rate** | _run and fill_ | _run and fill_ |

---

## Residual risks

- Novel paraphrased attacks may bypass regex (FM-2.3 in `failure_modes.md`).
- Regex runs on **output**, not input — a sophisticated attack that changes behaviour without leaving marker strings in output may pass.
- Empirical measurement on the 8 poisoned items is the authoritative score, not regex coverage alone.

---

## Where to inspect in the app

- **Security page** — KB inventory + session flags from the current run
- **Pipeline page** — flags expander after structuring/dedup
- **Evaluation page** — `is_injection` column in labeled-subset comparison table
