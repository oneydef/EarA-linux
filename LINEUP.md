# Nothing / CMF lineup — support status

EarA targets the **community RFCOMM family** used by compatible earbuds
(SDP-discovered channel, `0x55` frames, CRC-16/ARC). That is the same family Ear (web)
uses. It is **not** a guarantee that every SKU is fully tested on Linux,
and EarA is not an official vendor product.

## Status definitions

- **Reference device** — exercised end to end with EarA on Linux.
- **Confirmed** — the listed device replies were captured on real hardware.
- **Expected** — EarA has a matching profile or the vendor documents the feature,
  but no successful Linux report has confirmed it yet.
- **Unknown** — do not assume the feature works until a hardware report is available.

Audio playback is always handled by the host Bluetooth stack (BlueZ plus
PulseAudio/PipeWire), not by EarA. LHDC/LDAC availability depends on the adapter and
distro codecs.

## Matrix

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

## What “ready for the whole lineup” means

**Ready as a protocol platform:** yes, with per-model feature flags in
`eara/models.py`. Unknown devices receive only a provisional profile and must not be
presented as hardware-confirmed.

**Ready as a QA-complete companion:** no. Nothing Ear (a) is the end-to-end reference
device. CMF Buds 2 has confirmed battery, ANC and EQ support. Nothing Ear (3) has a
real protocol capture, while its dedicated EarA profile still needs hardware validation.
Every other SKU remains best-effort until a Linux report confirms it.

## Adding or confirming a model

1. Pair the device and run `eara status --json`.
2. Redact the Bluetooth address and most of the serial number before posting.
3. Report which controls work: battery, ANC, EQ, gestures, find, fit test and audio.
4. If the protocol does not connect, include a timestamped debug log or RFCOMM capture.
5. Map a SKU prefix only after the hardware identifier is confirmed. A Bluetooth-name
   fallback is provisional and must be labelled as such.

Open a [device support report](https://github.com/oneydef/EarA-linux/issues/new?template=device_support.yml)
or use [Discussions](https://github.com/oneydef/EarA-linux/discussions/categories/general).
