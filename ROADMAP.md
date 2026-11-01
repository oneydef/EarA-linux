# EarA roadmap

This roadmap describes the project's direction, not fixed release dates. Priorities may change as new devices are tested and contributors join the project.

## Shipped in EarA 0.6: interface and UI/UX refresh

EarA 0.6 delivers the first complete interface refresh: a fixed 1200×720 layout, consistent navigation and component styling, screen-aware themes, separate device details, real connection diagnostics, synchronized quick controls, corrected equalizer behavior, and simplified motion and feedback.

UI and UX remain a core project priority. Follow-up work includes:

- Validate the new navigation and recovery flows with real users and more device models.
- Refine the visual hierarchy, spacing system, and component style where testing exposes friction.
- Make connection, battery, audio-profile, and device states even easier to understand at a glance.
- Continue improving pairing, reconnection, error, and recovery guidance.
- Reduce friction in ANC, EQ, gesture, and device-management workflows.
- Improve behavior across display densities while preserving the verified 1200×720 workspace.
- Improve keyboard navigation, focus states, contrast, labels, and screen-reader support.
- Validate design changes with real users and iterate before treating the refresh as complete.

Future UI changes will be developed incrementally so device reliability and feature access remain intact.

## Near term: strengthen the Linux release

- Expand real-hardware testing across Nothing and CMF models.
- Improve Bluetooth reconnection, diagnostics, and recovery.
- Complete distribution work, including Flatpak and easier package updates.
- Improve translations, documentation, and automated tests.
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
