#!/usr/bin/env python3

import logging

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())


def main():
    import argparse
    import sys

    MODES = {
        "gui": run_gui,
    }

    parser = argparse.ArgumentParser("CADConversion Entrypoint")
    parser.add_argument("mode", choices={"gui"})
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true",
                        help="Output debug logging messages.")
    args = parser.parse_args()

    # Setup logging
    loglevel = logging.DEBUG if args.verbose else logging.INFO
    logfmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s")

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logfmt)
    logging.getLogger().setLevel(loglevel)
    logging.getLogger().addHandler(stderr_handler)

    LOG.debug(f"args: {vars(args)}")

    MODES[args.mode](args)


def run_gui(args):
    """Run the GUI mode."""
    from . import gui
    gui.mainwindow.run()


if __name__ == "__main__":
    main()
