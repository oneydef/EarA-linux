Nothing Ear (a) is EarA's end-to-end reference device. **CMF Buds 2** additionally has
confirmed battery, ANC and EQ support on Linux. **Nothing Ear (3)** has confirmed
protocol captures, while its dedicated EarA profile still awaits hardware validation.
Every other SKU is best-effort until a Linux report confirms it.

**How to help:** open a [Device support issue](https://github.com/oneydef/EarA-linux/issues/new?template=device_support.yml) or post in [Discussions → General](https://github.com/oneydef/EarA-linux/discussions/categories/general) with:

1. Product name + distro
2. `eara status --json` output (redact the Bluetooth address and most of the serial)
3. Checklist of what works / what does not

---

## Status definitions

- **Reference device** — exercised end to end with EarA on Linux.
- **Confirmed** — the listed device replies were captured on real hardware.
- **Expected** — EarA has a matching profile or the vendor documents the feature,
  but no successful Linux report has confirmed it yet.
- **Unknown** — do not assume the feature works until a hardware report is available.

## Support matrix

| Product | Base / profile | Audio (A2DP) | ANC | EQ / bass | Gestures | Fit test | QA status |
|---|---|---|---|---|---|---|---|
| Nothing Ear (1) | B181 | host BT | expected; no adaptive ANC | presets expected | expected | — | ❓ untested |
| Nothing Ear (stick) | B157 | host BT | **no ANC** | presets + custom expected | expected | — | ❓ untested |
| Nothing Ear (2) | B155 | host BT | full + personal ANC expected | presets + custom expected | expected | expected | ❓ untested |
| Nothing Ear (a) | B162 | host BT, tested | full, tested | presets + bass, tested | tested | tested | ✅ reference device |
| Nothing Ear (2024) | B171 | host BT | full expected | presets + bass expected | expected | expected | ❓ untested |
| Nothing Ear (open) | B174 | host BT | **no ANC** | 4 presets + custom expected | expected | no | ❓ EarA controls untested |
| CMF Buds | B168 | host BT | listening modes expected | presets + custom + bass expected | expected | — | ❓ untested |
| CMF Buds Pro | B163 | host BT | expected | presets + custom expected | expected | expected | ❓ untested |
| CMF Buds Pro 2 | B172 | host BT | full expected | 6 presets + custom + bass expected | expected | expected | ❓ untested |
| CMF Buds 2 | B179 | host BT, tested | high / off / transparency confirmed | 7 presets + custom EQ confirmed | unknown | — | ✅ battery / ANC / EQ confirmed; RFCOMM channel 16 |
| CMF Buds 2 Plus | unknown; name provisionally maps to B168 | host BT | unknown | unknown | unknown | unknown | 🧪 protocol not yet confirmed; see [#3](https://github.com/oneydef/EarA-linux/issues/3) |
| CMF Neckband Pro | B164 | host BT | expected | limited controls expected | expected | no | ❓ untested |
| Nothing Ear (3) | `ear3` profile pending | host BT | protocol confirmed; no personal ANC response | preset, custom EQ and bass protocol confirmed | protocol confirmed | unknown | 🧪 captures verified in [#29](https://github.com/oneydef/EarA-linux/issues/29); dedicated recognition awaits hardware validation in [#31](https://github.com/oneydef/EarA-linux/pull/31) |
| Newer / unmapped devices | unknown | host BT | unknown | unknown | unknown | unknown | ❓ needs device report and protocol dump |

**Audio** is provided by BlueZ plus PulseAudio/PipeWire. Codec availability depends on
the Bluetooth adapter and distro, not EarA.

Full details: [LINEUP.md](https://github.com/oneydef/EarA-linux/blob/main/LINEUP.md)

Latest release: [GitHub Releases](https://github.com/oneydef/EarA-linux/releases/latest) · [Flathub](https://flathub.org/apps/io.github.oneydef.eara)

---

## Report template (copy-paste)

```
Product:
Distro:
EarA version / install source:
Works: connect / battery / ANC / EQ / gestures / find / fit / A2DP / HFP
Broken:
eara status --json (redacted):
Notes:
```

Thank you — even a single confirmed row helps everyone on Linux.
