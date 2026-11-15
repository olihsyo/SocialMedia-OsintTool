# osintx

Single-target OSINT: give it one email address or one phone number and it maps the
public footprint — DNS/mail hygiene, breach exposure, mailbox liveness, and which
services have an account registered against the identifier.

Written in Go (concurrent engine) with a YAML site registry and a Python
enrichment helper. Ships a terminal view plus JSON and HTML reports.

---

## Requirements

| Tool | Why | Check |
|------|-----|-------|
| Go 1.22+ | builds the engine | `go version` |
| Python 3.9+ | offline phone enrichment | `python3 -V` |
| `phonenumbers` (optional) | carrier / region / line type | `pip install phonenumbers` |

Install Go: https://go.dev/dl/
The tool runs fine without `phonenumbers`; you just lose phone metadata.

---

## Install

```bash
cd ~/osintx
go mod tidy          # first run only, downloads deps
chmod +x run.sh
