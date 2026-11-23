# Orion-Core

Orion-Core is an experimental, read-only Windows diagnostics and software-compatibility research toolkit.

## Requirements

- Python 3.10 or newer
- Basic system report: Windows, Linux, or macOS
- Extended CPU/GPU and graphics-runtime inventory: Windows with PowerShell and access to the local Windows registry

## Run

From a source checkout:

```bash
python -m pip install -e .
python -m orion_core
```

Machine-readable report:

```bash
python -m orion_core --json
```

Skip Windows-specific inventory:

```bash
python -m orion_core --basic-only --json
```

## Windows inventory scope

The current Windows collector reads CPU and display-adapter properties through CIM, the DirectX registry version, and the count of registered Vulkan ICD manifest entries. These are diagnostic indicators, not a certification of game compatibility or a complete DirectX feature-level/Vulkan capability test. Missing data is reported rather than guessed.

The tool is read-only: it does not change registry values, install software or drivers, run downloaded executables, or collect device serial numbers, MAC addresses, usernames, hostnames, or personal files.

See [ROADMAP](docs/ROADMAP.md), [SAFETY](docs/SAFETY.md), and the [agent team charter](docs/AGENT_TEAM.md). Role prompts for compatible coding-agent environments are stored in `.github/agents/`.
