from pathlib import Path
import os
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


def run():
    if "--notifier" in sys.argv or "--notifier-once" in sys.argv:
        from enfermeria_app.notifier import main
        return main(once="--notifier-once" in sys.argv)
    if "--panel" in sys.argv and "--main" not in sys.argv:
        from enfermeria_app.panel import main
        return main()
    from enfermeria_app.main import main
    return main(smoke_test="--smoke-test" in sys.argv)


if __name__ == "__main__":
    if "--smoke-test" in sys.argv:
        # Configure isolation before importing config or opening any database.
        with TemporaryDirectory(prefix="enfermeria_startup_") as test_directory:
            os.environ["XDG_DATA_HOME"] = test_directory
            os.environ["XDG_CONFIG_HOME"] = test_directory
            os.environ["APPDATA"] = test_directory
            raise SystemExit(run())
    raise SystemExit(run())
