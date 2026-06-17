"""
Classification Banner - Main Entry Point
"""
import sys
import traceback
import classification_banner as cb


def main():
    """Main entry point"""
    print(cb.__version__)
    cb.eventlog.log_info(f"ClassificationBanner {cb.__version__} starting")
    banner = cb.banner.ClassificationBanner()

    if banner.settings.enabled:
        banner.run()
    else:
        print("Classification banner is disabled in registry (Enabled=0)")
        sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        # Normal exit path (e.g. banner disabled) — not a crash.
        raise
    except BaseException:
        # The exe is windowed (console=False), so an unhandled exception
        # would otherwise vanish without a trace. Record it to the Windows
        # event log so the exit is diagnosable, then re-raise.
        cb.eventlog.log_error(
            "ClassificationBanner exited on an unhandled exception:\n"
            + traceback.format_exc()
        )
        raise
