# research-pro (Dev-only)

This directory contains development-only validation for the `research-pro` skill.
It stays outside the installable skill directory so installations keep only the
runtime browser wrapper and skill instructions.

## Quick smoke

From the repo root:

```sh
python3 dev/research-pro/run_smoke.py
```

This smoke entrypoint validates the `agent-browser-node.sh` wrapper without
opening a browser session:

- no-args usage exits with the documented code and usage text
- `AGENT_BROWSER_JS_PATH` passthrough executes a temporary JS wrapper under Node
- wrapper arguments are forwarded unchanged to the JS entrypoint
