import sys


def _run_python_c() -> None:
    """Behave like `python -c CODE` when a library re-launches sys.executable.

    In the app bundle sys.executable is the app stub, so e.g. multiprocessing's
    resource tracker (`<exe> -B -I -c "..."`) would otherwise start another app.
    """
    args = sys.argv[1:]
    code = args[args.index("-c") + 1]
    sys.argv = ["-c", *args[args.index("-c") + 2 :]]
    exec(compile(code, "<string>", "exec"), {"__name__": "__main__"})
    sys.exit(0)


if __name__ == "__main__":
    if "-c" in sys.argv[1:]:
        _run_python_c()

    from whisper_batch_app.app import main

    main().main_loop()
