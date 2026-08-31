# Nothing / CMF lineup — support status

EarA targets the **community RFCOMM family** used by compatible earbuds
(channel 15, `0x55` frames, CRC-16/ARC). That is the same family Ear (web)
uses. It is **not** a guarantee that every SKU is fully tested on Linux,
and EarA is not an official vendor product.

## Matrix

| Product | Base | Audio (A2DP) | ANC | EQ / bass | Gestures | Fit test | Notes |
|---|---|---|---|---|---|---|---|
| Nothing Ear (1) | B181 | host BT | yes (no adaptive) | presets only | yes | — | |
| Nothing Ear (stick) | B157 | host BT | limited | yes | yes | — | |
| Nothing Ear (2) | B155 | host BT | full + personal ANC | yes | yes | yes | protocol origin |
| Nothing Ear (a) | B162 | **tested** | full | presets + bass | yes | yes | this repo’s reference device |
| Nothing Ear (2024) | B171 | host BT | full | yes + bass | yes | yes | same family as Ear (a) |
| Nothing Ear (open) | B174 | host BT | no | limited | limited | no | open-ear; untested here |
| CMF Buds | B168 | host BT | via listening mode | listening + bass | yes | — | |
| CMF Buds Pro | B163 | host BT | yes | yes | yes | yes | |
| CMF Buds Pro 2 | B172 | host BT | yes | listening + bass | yes | yes | |
| CMF Neckband Pro | B164 | host BT | yes | limited | limited | no | untested |
| Ear (3) / newer | ? | unknown | unknown | unknown | unknown | — | add SKU when dumps exist |

**Audio** is always the host stack (BlueZ + PulseAudio/PipeWire). LHDC/LDAC
depend on the dongle and distro codecs, not on this app.

## What “ready for the whole lineup” means

**Ready as a protocol platform:** yes, with per-model feature flags in
`eara/models.py`. Unknown devices still get conservative controls (battery,
ANC, EQ, latency, find).

**Ready as a QA-complete companion:** no. Only Ear (a) has been exercised
end-to-end on Linux in this tree. Other SKUs need:

1. A serial/SKU dump from `eara status --json`
2. Confirmation of ANC / EQ / gesture replies
3. Optional: RFCOMM capture if a command is ignored

## Adding a new model

1. Pair the device, run `eara status --json`, collect `serial` and firmware.
2. Map SKU prefix → `base` in `SKU_PREFIX_TO_BASE`.
3. Set capability flags on `Model`.
4. Open an issue with the JSON if a control does nothing.

Newer Nothing products that switch to LE Audio / LC3-only will need a
**different transport**, not just new command IDs.
