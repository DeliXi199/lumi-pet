import sys

try:
    from pet.qt_app import main
except ImportError as exc:
    if getattr(exc, "name", "") and str(exc.name).startswith("PySide6"):
        from desktop_pet import DesktopPet

        def main():
            self_test = "--self-test" in sys.argv
            smoke_test = "--smoke-test" in sys.argv
            DesktopPet(self_test=self_test, smoke_test=smoke_test).run()
    else:
        raise


if __name__ == "__main__":
    main()
