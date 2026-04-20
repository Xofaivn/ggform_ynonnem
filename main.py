from ui.wizard import run_wizard
from core.filler import run_all


def main() -> None:
    config = run_wizard()
    run_all(config)


if __name__ == "__main__":
    main()
