# Contributing to EarA

EarA is an **unofficial** community companion for Nothing / CMF earbuds on Linux.
It is not affiliated with Nothing Technology or CMF.

## Before you open a PR

1. Test against a paired device when possible (Nothing Ear (a) is the reference SKU).
2. Run the test suite:
   ```bash
   python3 -m unittest discover -s tests -v
   ```
3. Keep changes focused — match existing style in `eara/`.
4. If you add i18n keys, update **both** `en` and `uk` in `eara/i18n.py` (CI checks key parity).

## Reporting issues

| Channel | Use for |
|---------|---------|
| [Bug report](https://github.com/oneydef/EarA-linux/issues/new?template=bug_report.yml) | Crashes, broken controls, install failures |
| [Device support](https://github.com/oneydef/EarA-linux/issues/new?template=device_support.yml) | “Works on my Ear (2)” with `eara status --json` |
| [Q&A Discussions](https://github.com/oneydef/EarA-linux/discussions/categories/q-a) | Distro setup, usage questions |
| [General Discussions](https://github.com/oneydef/EarA-linux/discussions/categories/general) | Informal device reports, tips |

Always include `eara doctor` for bugs and `eara status --json` for device reports when you can.

## Adding a new earbuds model

1. Pair the device and run `eara status --json`.
2. Map the serial prefix in `eara/models.py` (`SKU_PREFIX_TO_BASE`).
3. Set capability flags on the `Model` dataclass.
4. Open a **Device support** issue or PR with your JSON dump and test notes.

See [LINEUP.md](LINEUP.md) for the current matrix.

## License

By contributing, you agree that your contributions are licensed under
**GPL-3.0-or-later**, the same license as the project.
