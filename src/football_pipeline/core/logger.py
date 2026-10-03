import logging
import sys


def setup_logger() -> None:
    """Configures the root logger for the entire pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s",
    )
