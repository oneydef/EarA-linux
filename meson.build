project(
  'eara',
  version: '0.6.2',
  meson_version: '>=0.60.0',
)

app_id = 'io.github.oneydef.eara'
eara_data_dir = get_option('datadir') / 'eara'

# Keep the Python sources and runtime assets in one relocatable application
# directory.  The launcher adds this directory to PYTHONPATH before starting
# EarA, matching the layout used by the portable packages.
install_subdir(
  'eara',
  install_dir: eara_data_dir,
  exclude_directories: ['__pycache__'],
)

install_subdir(
  'packaging/fonts',
  install_dir: eara_data_dir / 'packaging',
)
install_subdir(
  'packaging/ui',
  install_dir: eara_data_dir / 'packaging',
)
install_subdir(
  'packaging/screenshots',
  install_dir: eara_data_dir,
)

install_data(
  'flatpak/io.github.oneydef.eara',
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x',
)
install_data(
  'flatpak/io.github.oneydef.eara.desktop',
  install_dir: get_option('datadir') / 'applications',
)
install_data(
  'flatpak/io.github.oneydef.eara.metainfo.xml',
  install_dir: get_option('datadir') / 'metainfo',
)
install_data(
  'packaging/eara.svg',
  install_dir: get_option('datadir') / 'icons/hicolor/scalable/apps',
  rename: app_id + '.svg',
)
install_data(
  'LICENSE',
  install_dir: get_option('datadir') / 'licenses' / app_id,
)
