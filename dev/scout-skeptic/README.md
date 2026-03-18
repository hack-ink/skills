# scout-skeptic maintainer checks

This dev directory validates the hard-cut source surface for `scout-skeptic`.

Run:

```bash
python3 dev/scout-skeptic/run_smoke.py
```

The smoke test checks that:

- the new `scout-skeptic` skill exists
- the deleted `multi-agent` source surface is gone
- repo docs point to `scout-skeptic`

Runtime source validation lives separately under:

```bash
python3 dev/smoke/codex/run_scout_skeptic_source_smoke.py
```

Run that command from the nix repo that owns the `home/codex/` source tree.
