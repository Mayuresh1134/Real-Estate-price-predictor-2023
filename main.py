"""Start HomeValueVision:  python main.py"""
import sys


def main() -> None:
    try:
        import customtkinter  # noqa: F401
        import sklearn  # noqa: F401
    except ImportError as missing:
        sys.exit(f"A required package is missing ({missing.name}).\n"
                 "Install everything with:  pip install -r requirements.txt")
    from hvv.ui.app import run
    run()


if __name__ == "__main__":
    main()
