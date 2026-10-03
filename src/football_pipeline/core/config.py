import logging
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def load_config(config_path: str | Path, env_path: str | Path) -> dict:
    """
    Loads YAML configuration and injects required environment variables.

    Reads the static configuration from the specified YAML file and
    supplements it with dynamic secrets loaded from the environment
    or a provided .env file.

    Args:
        config_path (str | Path): Path to the static config.yaml file.
        env_path (str | Path): Path to the .env file.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        yaml.YAMLError: If the YAML file is malformed.
        KeyError: If a required environment variable is missing.
        PermissionError: If there are insufficient permissions to read the file.

    Returns:
        dict: Parsed and consolidated configuration data.
    """
    # Silently ignores if .env is missing (expected in Docker/cloud environments)
    load_dotenv(env_path)
    config_path = Path(config_path)

    try:
        config = yaml.safe_load(config_path.read_text())
        config["api_football_key"] = os.environ["API_FOOTBALL_KEY"]
        config["aws_s3_landing_bucket"] = os.environ["AWS_S3_LANDING_BUCKET_NAME"]
    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        raise
    except KeyError as e:
        logger.error(f"Missing environment variable: {e}")
        raise
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file: {e}")
        raise
    except PermissionError as e:
        logger.error(f"Permission denied when accessing the configuration file: {e}")
        raise

    return config
