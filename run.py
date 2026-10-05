from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

if "--notifier" in sys.argv or "--notifier-once" in sys.argv:
    from enfermeria_app.notifier import main
elif "--panel" in sys.argv:
    from enfermeria_app.panel import main
else:
    from enfermeria_app.main import main

if __name__ == "__main__":
    raise SystemExit(main(once="--notifier-once" in sys.argv) if "--notifier" in sys.argv or "--notifier-once" in sys.argv else main())
