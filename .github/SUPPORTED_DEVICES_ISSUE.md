EarA is tested end-to-end on **Nothing Ear (a)** only. Every other SKU in the same RFCOMM family is *best-effort* until someone confirms it on Linux.

**How to help:** open a [Device support issue](https://github.com/oneydef/EarA-linux/issues/new?template=device_support.yml) or post in [Discussions → General](https://github.com/oneydef/EarA-linux/discussions/categories/general) with:

1. Product name + distro
2. `eara status --json` output
3. Checklist of what works / what does not

---

## Support matrix

| Product | Base | Audio (A2DP) | ANC | EQ / bass | Gestures | Fit test | QA status |
|---|---|---|---|---|---|---|---|
| Nothing Ear (1) | B181 | host BT | yes (no adaptive) | presets only | yes | — | ❓ untested |
| Nothing Ear (stick) | B157 | host BT | limited | yes | yes | — | ❓ untested |
| Nothing Ear (2) | B155 | host BT | full + personal ANC | yes | yes | yes | ❓ untested |
| Nothing Ear (a) | B162 | **tested** | full | presets + bass | yes | yes | ✅ reference device |
| Nothing Ear (2024) | B171 | host BT | full | yes + bass | yes | yes | ❓ untested |
| Nothing Ear (open) | B174 | host BT | no | limited | limited | no | ❓ untested |
| CMF Buds | B168 | host BT | via listening mode | listening + bass | yes | — | ❓ untested |
| CMF Buds Pro | B163 | host BT | yes | yes | yes | yes | ❓ untested |
| CMF Buds Pro 2 | B172 | host BT | yes | listening + bass | yes | yes | ❓ untested |
| CMF Neckband Pro | B164 | host BT | yes | limited | limited | no | ❓ untested |
| Ear (3) / newer | ? | unknown | unknown | unknown | unknown | — | ❓ needs dumps |

**Audio** = host stack (BlueZ + PulseAudio/PipeWire). LHDC/LDAC depends on your adapter, not EarA.

Full details: [LINEUP.md](https://github.com/oneydef/EarA-linux/blob/main/LINEUP.md)

---

## Report template (copy-paste)

```
Product:
Distro:
Works: connect / battery / ANC / EQ / gestures / find / fit / A2DP / HFP
Broken:
eara status --json:
Notes:
```

Thank you — even a single confirmed row helps everyone on Linux.
