# EarA roadmap

This roadmap describes the project's direction, not fixed release dates. Priorities may change as new devices are tested and contributors join the project.

## Near term: strengthen the Linux release

- Expand real-hardware testing across Nothing and CMF models.
- Improve Bluetooth reconnection, diagnostics, and recovery.
- Complete distribution work, including Flatpak and easier package updates.
- Improve accessibility, translations, documentation, and automated tests.
- Keep the GUI and CLI aligned as new controls are added.

## Cross-platform foundation

Before adding another operating system, EarA needs a reusable core separated from Linux-specific integrations:

- Isolate the earbud protocol, device state, and command handling from the GTK UI.
- Define platform adapters for Bluetooth discovery, RFCOMM communication, and audio routing.
- Add protocol fixtures and tests that can run without connected earbuds.
- Document which features depend on BlueZ, PipeWire, or other Linux-only services.

## Planned: macOS support

The first non-Linux target is planned to be macOS. Work will include:

- A macOS Bluetooth transport compatible with the EarA protocol.
- Integration with Core Audio for host audio profiles and routing where supported.
- A native-feeling application package and signing/notarization workflow.
- Hardware testing on Apple Silicon and current macOS releases.

## Planned: Windows support

Windows support is also planned after the shared core is stable. Work will include:

- A Windows Bluetooth transport and reliable device discovery.
- Integration with Windows audio-device and profile APIs where supported.
- A Windows desktop UI or an appropriate cross-platform frontend.
- Signed installer packages and testing on supported Windows releases.

## Important limitations

Feature parity is not guaranteed across operating systems. Bluetooth and audio APIs expose different capabilities, and some controls may require platform-specific research. Linux remains the reference implementation while macOS and Windows support are developed.

## Contributing

Contributions are welcome, especially from developers with macOS or Windows Bluetooth experience and access to Nothing or CMF earbuds. Before starting a large platform port, please open an issue so the architecture and scope can be discussed.

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [device lineup](LINEUP.md).
