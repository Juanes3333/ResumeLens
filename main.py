"""Entry point of ResumeLens: ``python main.py --cv <resume.txt> [--profile NAME] [--output FILE]``."""

import sys

from resumelens.cli import main

if __name__ == "__main__":
    sys.exit(main())
