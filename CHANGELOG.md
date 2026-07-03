# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.2] - 2026-07-02

### Fixed
- Re-flow already-maximized windows when the AppBar is registered. A window
  maximized while the workstation is locked fills the full screen (no AppBar is
  running); on unlock the banner relaunched and reserved its space, but Windows
  does not re-flow windows that were *already* maximized, so they overlapped the
  banner. The banner now enumerates maximized top-level windows and resizes each
  to its monitor's reduced work area (without stealing focus or changing
  z-order). Also covers registry- and monitor-change banner recreation.

## [1.4.1] - 2026

### Fixed
- Relaunch the banner on workstation unlock, not just at logon.

## [1.4.0] - 2026

### Added
- Windows event-log channel for banner diagnostics.

### Fixed
- Sleep/resume crash resilience: transient monitor-enumeration and
  registry-check errors are caught so they can no longer tear down the Tk main
  loop.

## Earlier

- Installer uses a scheduled task at logon instead of an HKLM `Run` key.
- GPO-controlled fullscreen banner suppression with an audit log.
- GPO controls for font size, banner height, and font family.
- Banners are recreated after a monitor/resolution change.

[1.4.2]: https://github.com/192d-Wing/ClassificationBanner/releases/tag/v1.4.2
[1.4.1]: https://github.com/192d-Wing/ClassificationBanner/releases/tag/v1.4.1
[1.4.0]: https://github.com/192d-Wing/ClassificationBanner/releases/tag/v1.4.0
