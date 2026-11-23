# Orion-Core

Orion-Core is an experimental, read-only Windows diagnostics and software-compatibility research toolkit.

The first milestone collects basic system facts and can emit a JSON report. It does not change system settings, install drivers, execute third-party programs, or inspect personal files.

## Requirements

- Python 3.10 or newer
- Windows, Linux, or macOS for the basic system report

## Run

```bash
python -m orion_core
```

From a source checkout:

```bash
python -m pip install -e .
orion-core --json
```

## Project status

Early development. Hardware and graphics API inventory, structured compatibility checks, and a reproducible test harness are planned; they are not yet implemented.

See [ROADMAP](docs/ROADMAP.md) and [SAFETY](docs/SAFETY.md).
