# DeskClip MVP Design Spec

Date: 2026-04-23
Status: Draft for user review

## Purpose

DeskClip is a DeskClaw-compatible clipboard memory skill. It lets DeskClaw help users find previously copied content, especially risky or important snippets such as API keys, commands, URLs, JSON, code, and notes.

The product promise for the MVP is:

> Understand copied content, manage clipboard risk, and make clipboard memory searchable.

## Recommended Shape

Use a self-bootstrapping DeskClaw skill package with a local CLI core and a lightweight detached watcher.

```text
deskclip/
|- _meta.json
|- SKILL.md
`- scripts/
   |- install.sh
   |- install.ps1
   |- deskclip.py
   |- start.sh
   |- stop.sh
   |- status.sh
   |- capture.sh
   |- search.sh
   |- inspect.sh
   |- copy.sh
   |- pending.sh
   `- annotate.sh
```

The skill does not keep a DeskClaw invocation open forever. `start.sh` starts a detached local watcher and returns immediately.

## Responsibilities

DeskClip CLI owns:

- Reading text from the system clipboard.
- Falling back from Python clipboard libraries to platform commands.
- Rule-based classification and secret detection.
- Fernet encryption of original clipboard content.
- SQLite storage of searchable metadata.
- Detached watcher lifecycle through pid, heartbeat, status, and logs.
- Search, inspect, and copy-back operations.

DeskClaw owns:

- Natural-language parsing into structured search parameters.
- AI understanding of safe analysis payloads.
- Calling `pending.sh` and writing AI annotations back through `annotate.sh`.
- Deciding when to call `start.sh`, `status.sh`, `search.sh`, and `copy.sh`.

## MVP Flow

```text
install
-> initialize local runtime directory
-> create venv if needed
-> install cryptography
-> initialize SQLite
-> initialize Fernet master key

start
-> check pid and heartbeat
-> start watcher if missing
-> return immediately

watcher
-> poll clipboard
-> hash and dedupe
-> classify locally
-> detect secrets locally
-> encrypt original text
-> write metadata and encrypted blob
-> mark record as analysis_pending

DeskClaw AI
-> read pending safe payloads
-> analyze non-sensitive content
-> analyze only masked metadata for sensitive content
-> write annotations back

search
-> query time, kind, secret_type, tags, title, preview, risk
-> return masked results

copy
-> decrypt selected content
-> write it back to the system clipboard
```

## Commands

```bash
./scripts/install.sh
./scripts/start.sh
./scripts/status.sh
./scripts/capture.sh
./scripts/pending.sh --limit 10
./scripts/annotate.sh <id> --title "OpenAI API key" --tags openai,api-key,secret --risk high
./scripts/search.sh --since 3d --kind secret_candidate --secret-type openai_api_key
./scripts/inspect.sh <id>
./scripts/copy.sh <id>
./scripts/stop.sh
```

Windows uses `install.ps1`; other wrapper scripts may call the same Python CLI through the local venv.

## Data Storage

Default local directory:

```text
~/.deskclaw/deskclip/
|- clips.sqlite
|- blobs/
|- deskclip.key
|- deskclip.pid
|- heartbeat.json
`- logs/
```

SQLite stores only searchable metadata and encrypted blob references. Original clipboard content must not be stored in plaintext.

Minimum clip fields:

- `id`
- `created_at`
- `kind`
- `secret_type`
- `masked_preview`
- `content_hash`
- `encrypted_blob_path` or encrypted blob field
- `ai_title`
- `ai_summary`
- `ai_tags`
- `risk_level`
- `analysis_status`
- `metadata_json`

## Clipboard Scope

MVP supports text clipboard content only.

Supported classification targets:

- `text`
- `url`
- `json`
- `markdown`
- `code`
- `command`
- `path`
- `secret_candidate`

Supported secret subtypes:

- `openai_api_key`
- `github_token`
- `jwt`
- `aws_access_key`
- `bearer_token`
- `generic_api_key`

Not in MVP:

- Real file-object clipboard reads.
- Image clipboard reads or OCR.
- Rich text preservation.
- GUI, tray, global shortcuts.
- Vector search.
- Cloud sync.
- Full secret plaintext exposure to AI.

## Clipboard Reading Strategy

Use a hybrid reader:

1. Try a Python clipboard library first.
2. If it fails, use platform commands.

Fallback commands:

- macOS: `pbpaste` and `pbcopy`
- Linux: `wl-paste` / `wl-copy`, then `xclip` / `xsel`
- Windows: PowerShell `Get-Clipboard` and `Set-Clipboard`

Uncertainty: the exact Python clipboard library is not fixed in this spec. `pyperclip` is the likely default, but implementation should verify cross-platform behavior before locking it.

## Encryption

Use `cryptography.Fernet`.

Key precedence:

1. `DESKCLIP_MASTER_KEY` environment variable.
2. Local key file at `~/.deskclaw/deskclip/deskclip.key`.

The installer creates the key file if neither source exists.

Security rule: original clipboard content is encrypted before storage. Search, inspect, pending analysis, and normal result output must use masked previews unless `copy` explicitly restores the selected record to the system clipboard.

Uncertainty: key file permission handling must be implemented per platform and verified. This MVP does not claim enterprise-grade key management.

## AI Safety Contract

DeskClip does not run AI itself. It exposes safe payloads to DeskClaw.

For non-sensitive content, `pending.sh` may return enough text for DeskClaw to generate:

- title
- summary
- tags
- memory hints
- risk level

For sensitive content, `pending.sh` must not return plaintext. It returns only:

- masked preview
- secret subtype
- length
- timestamps
- local rule matches
- non-sensitive metadata

DeskClaw writes results through `annotate.sh`.

## Watcher Strategy

Use solution 3: lightweight supervisor.

`start.sh` behavior:

- Check pid and heartbeat.
- If watcher is alive, return existing status.
- If watcher is dead or missing, launch a detached watcher and return.
- Avoid starting duplicate watchers.

`status.sh` returns:

- `running` or `stopped`
- pid
- last heartbeat time
- last capture time
- database path
- log path

`stop.sh` stops the watcher using the pid file.

Uncertainty: process detachment differs across platforms. MVP should implement the simplest reliable approach per platform and expose clear failure output.

## Search Model

DeskClaw parses natural language into structured CLI options. DeskClip does not implement natural-language parsing in MVP.

Example:

User asks:

> Find the OpenAI key I copied three days ago.

DeskClaw calls:

```bash
./scripts/search.sh --since 3d --kind secret_candidate --secret-type openai_api_key
```

Search uses SQLite metadata, masked preview, AI tags, AI title, and risk fields. It should not decrypt every record for normal search.

## MVP Acceptance Criteria

- `install` initializes runtime directory, SQLite, venv, `cryptography`, and Fernet key.
- `start` launches watcher and returns immediately.
- Repeated `start` calls do not create duplicate watchers.
- `status` reports watcher state and heartbeat.
- `capture` stores a text clipboard item without plaintext in SQLite.
- Secret-like content is classified as `secret_candidate`.
- OpenAI-style keys are classified as `openai_api_key`.
- `pending` redacts sensitive content.
- `annotate` writes DeskClaw AI title, tags, summary, and risk level.
- `search` can find a secret by time range and secret subtype.
- `inspect` defaults to masked output.
- `copy` decrypts and restores selected content to the clipboard.

## Implementation Risks

- Installing `cryptography` may require network access or compatible wheels.
- Clipboard fallback commands vary by OS and desktop environment.
- Detached watcher behavior may be affected by DeskClaw sandboxing.
- Local key file protection is only as strong as local filesystem permissions.
- AI annotations depend on DeskClaw calling `pending` and `annotate` correctly.

## Recommended MVP Cut

Build the self-bootstrapping skill package and CLI core first, with text-only clipboard support and rule-based risk detection. Keep AI inside DeskClaw via the `pending` and `annotate` protocol. Do not implement GUI, real file-object clipboard support, image support, or vector search until the text memory loop is reliable.
