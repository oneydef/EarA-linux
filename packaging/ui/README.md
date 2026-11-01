# EarA UI assets

The native GTK interface now reuses the approved source images directly:

- `reference-dashboard.png` is an unchanged copy of `docs/mockups/ui-refresh-device-dashboard.png`.
- `reference-recovery.png` is an unchanged copy of `docs/mockups/ui-refresh-connection-recovery-light.png`.

`eara/ui_widgets.py` crops the brand mark and illustration rectangles at runtime.
Device names, battery values, statuses, labels and all controls remain live native
widgets. The illustration crops retain the source background texture; they are
not transparent source vectors. Their appearance in the opposite theme is a
known limitation documented in the visual audit.

The older `earbuds-dashboard.png`, `earbuds-case.png`, `recovery-case.png`,
`recovery-button.png` and `recovery-refresh.png` were generated during the earlier
approximation. The current native interface no longer uses them. They remain for
compatibility with previous demos. No new generated artwork was used for this audit.

The packaged Inter font is used for conventional text. The constant EarA logo is
reused from each approved image. Live model names use a Cairo circular-dot mask;
this is explicitly not the original editable Nothing dotted typeface.
