# PRD: curator — AI-powered issue triage for Linear

**Author**: Fernando + Claude
**Date**: 2026-03-26
**Status**: Draft

## Problem

Issues accumulate without labels. Without labels, issues are invisible to filtered views, skills, and automation. Manual labeling is tedious — you have to open Linear, read each issue, decide the label, assign it. Nobody does it consistently.

The previous solution (`linear-curator`) ran a nightly LLM classification and sent a Telegram message saying "review these manually." But the message was a dead end — you couldn't act from Telegram. You had to open Linear, find the issue, decide. Too much friction. Issues stayed unlabeled.

## Solution

`curator` is a Python service that:

1. **Classifies** unlabeled issues using an LLM (via OpenRouter)
2. **Auto-applies** labels when confidence is high (≥ 85%)
3. **Asks for review via Telegram** when confidence is medium (50-84%) — with inline buttons so you can approve or override with one tap
4. **Learns from corrections** — every override becomes a few-shot example for the next classification

## Core principle

**Telegram is the review interface, not just a notification channel.** The message IS the action. One tap to accept, one tap to override. No context switching.

## Architecture

```
┌─────────────┐     ┌─────────┐     ┌────────┐
│  Classifier  │────▶│   lql   │────▶│ Linear │
│  (LLM)      │     │  (CLI)  │     │  (API) │
└──────┬──────┘     └─────────┘     └────────┘
       │
       ▼
┌─────────────┐     ┌───────────────┐
│  Telegram   │◀───▶│  Bot listener │
│  (user)     │     │  (webhooks)   │
└─────────────┘     └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │ corrections   │
                    │  .jsonl       │
                    └───────────────┘
```

### Key design decisions

1. **curator does NOT talk to Linear directly.** It uses `lql` for all Linear operations (`lql list --json`, `lql update --label X`, `lql comment`). Unix composition.

2. **Telegram bot runs as a systemd service on wuwei.** Long-running process that listens for button callbacks. When a button is pressed, it calls `lql` and responds.

3. **The classifier is a batch job.** Runs on a timer (nightly or on-demand). Classifies all unlabeled issues, auto-applies high-confidence ones, sends Telegram messages for medium-confidence ones.

4. **corrections.jsonl is the learning memory.** Append-only file. Each correction is a few-shot example loaded into the next classification prompt. No fine-tuning, no database. A file you can read, edit, and version.

## UX: Telegram review

### What the user sees

For each issue needing review, a Telegram message:

```
📋 PROD-618
"Configurar cron nocturno en wuwei"

Suggested: blog (71%)
Reason: "mentions pipeline and cron"

[✅ blog] [🏷 wuwei] [🏷 workflows] [🏷 infra] [⏭ skip]
```

The buttons show:

- The suggested label (with ✅)
- 3-4 most likely alternatives (from the classifier's second/third choices)
- Skip

### What happens on tap

- **Accept (✅ blog)**: `lql update PROD-618 --label blog`. No correction saved (classifier was right).
- **Override (🏷 wuwei)**: `lql update PROD-618 --label wuwei`. Correction saved to `corrections.jsonl`.
- **Skip (⏭)**: Do nothing. Issue stays unlabeled. Won't be re-suggested for 7 days (cooldown).

### Response

After tap:

```
✓ PROD-618 → wuwei
  (corrected from blog — saved as feedback)
```

### Bulk operations

Daily digest message (sent after classification):

```
🏷 Curator Report

Auto-applied: 8 issues
  PROD-620 → tokamak (92%)
  PROD-621 → blog (89%)
  ...

Pending review: 3 issues
  (individual messages sent above)

Skipped: 1 issue (confidence < 50%)
```

## UX: CLI review (alternative)

For when you're already in the terminal:

```bash
curator review              # list pending
curator review --accept-all --min-confidence 0.75
curator review PROD-618 --accept
curator review PROD-618 --label wuwei
curator review PROD-618 --skip
```

The CLI reads pending reviews from Linear (issues with curator suggestion comments that still have no label).

## Learning: corrections.jsonl

Format:

```jsonl
{"issue":"PROD-618","title":"Configurar cron nocturno en wuwei","suggested":"blog","corrected":"wuwei","confidence":0.71,"reason":"infra task not content","timestamp":"2026-03-26T22:00:00Z"}
{"issue":"CONT-42","title":"Post sobre zoxide","suggested":"workflows","corrected":"blog","confidence":0.63,"reason":"it's a blog post about a tool","timestamp":"2026-03-26T22:01:00Z"}
```

### How learning works

1. Classifier loads last N corrections (default: 30) as few-shot examples in the prompt
2. Each example shows: title → what was suggested → what was correct → why
3. Over time, the classifier learns patterns like "cron/pipeline in PRIV = wuwei, not workflows" or "post sobre X = blog, not the tool's label"
4. The `reason` field is key — it teaches the classifier the WHY, not just the WHAT

### Measuring learning

Track correction rate over time:

```
Week 1: 12 auto, 8 review, 5 corrected (62% accuracy on reviews)
Week 4: 15 auto, 4 review, 1 corrected (75% accuracy on reviews)
Week 8: 18 auto, 2 review, 0 corrected (100% accuracy on reviews)
```

If the correction rate doesn't decrease over time, the learning isn't working. This is the KPI.

## Stack

- **Python 3.12+** with uv
- **python-telegram-bot** — async Telegram bot with inline keyboards
- **openai** SDK (pointing to OpenRouter) — LLM classification
- **lql** — all Linear operations (subprocess calls)
- **systemd** — bot service on wuwei
- **cron/systemd timer** — nightly classification

## Data

```
~/.local/share/curator/
├── corrections.jsonl    # learning memory (append-only)
└── cooldowns.json       # skipped issues + expiry dates
```

## Configuration

```toml
# ~/.config/curator/config.toml

[classifier]
model = "anthropic/claude-sonnet-4-5"
auto_threshold = 0.85
review_threshold = 0.50
max_corrections = 30     # few-shot examples to load

[telegram]
bot_token_ref = "op://FRR DEV/Telegram Bot/bot-token"
chat_id_ref = "op://FRR DEV/Telegram Bot/group-id"

[lql]
binary = "lql"           # or full path
teams = ["PROD", "TOOL", "CONT", "PRIV", "KC"]

[labels]
# Product labels (the ones curator assigns)
product = ["tokamak", "qualitra", "rustyclaw", "beacon", "eoc", "autocorrect", "wuwei", "grokk", "kc_raven", "lql"]
# Domain labels
domain = ["blog", "rrss", "podcast", "producción-video", "workflows", "claude-code", "carrera", "aprendizaje", "gestión"]
```

## Phases

### Phase 1 — Classify + Telegram review

- Classifier (batch job): fetch unlabeled → LLM classify → auto-apply or send to Telegram
- Telegram bot: inline keyboards, accept/override/skip, corrections saved
- corrections.jsonl: append-only, loaded as few-shot
- Deploy on wuwei as systemd service + timer

### Phase 2 — CLI review + analytics

- `curator review` CLI (alternative to Telegram)
- `curator stats` — correction rate over time, accuracy trends
- `curator retrain` — rebuild few-shot cache from corrections
- Cooldown system for skipped issues

### Phase 3 — Integration

- Integrate with memento (show pending reviews in session start)
- Digest improvements (weekly summary, accuracy report)
- Multi-label support (suggest product + domain label)

## What curator does NOT do

- **Talk to Linear directly.** That's lql's job.
- **Fine-tune models.** Few-shot with corrections.jsonl is enough.
- **Replace human judgment.** It suggests. You decide (with one tap).
- **Cache Linear data.** Every run fetches fresh from lql.
