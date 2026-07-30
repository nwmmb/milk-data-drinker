import sys

if "--cli" in sys.argv:
    sys.argv.remove("--cli")
    from .cli import main
else:
    from .gui import main

main()
