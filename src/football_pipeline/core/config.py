import logging
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "config.yaml"
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"


def load_env(env_path: str | Path | None = None) -> None:
    """
    Loads variables from an env file without overriding those already set.

    A missing file is ignored, as containers get their variables from the
    orchestrator.

    Args:
        env_path (str | Path | None): Path to the env file. Defaults to
            PIPELINE_ENV_PATH, then to .env in the project root.
    """
    load_dotenv(env_path or os.environ.get("PIPELINE_ENV_PATH") or DEFAULT_ENV_PATH)


def read_config(config_path: str | Path | None = None) -> dict:
    """
    Reads the static YAML configuration, without any secrets.

    Args:
        config_path (str | Path | None): Path to the static config.yaml file.
            Defaults to PIPELINE_CONFIG_PATH, then to configs/config.yaml.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        yaml.YAMLError: If the YAML file is malformed.
        PermissionError: If there are insufficient permissions to read the file.

    Returns:
        dict: Parsed configuration data.
    """
    config_path = Path(
        config_path or os.environ.get("PIPELINE_CONFIG_PATH") or DEFAULT_CONFIG_PATH
    )

    try:
        return yaml.safe_load(config_path.read_text())
    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        raise
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file: {e}")
        raise
    except PermissionError as e:
        logger.error(f"Permission denied when accessing the configuration file: {e}")
        raise


def load_config(
    config_path: str | Path | None = None, env_path: str | Path | None = None
) -> dict:
    """
    Loads YAML configuration and injects required environment variables.

    The optional API_DELAY_SECONDS variable overrides api.limits.delay_seconds.

    Reads the static configuration from the specified YAML file and
    supplements it with dynamic secrets loaded from the environment
    or a provided .env file.

    Args:
        config_path (str | Path | None): Path to the static config.yaml file.
            Defaults to PIPELINE_CONFIG_PATH, then to configs/config.yaml.
        env_path (str | Path | None): Path to the env file, see load_env.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        yaml.YAMLError: If the YAML file is malformed.
        KeyError: If a required environment variable is missing.
        PermissionError: If there are insufficient permissions to read the file.

    Returns:
        dict: Parsed and consolidated configuration data.
    """
    load_env(env_path)
    config = read_config(config_path)

    try:
        config["api_football_key"] = os.environ["API_FOOTBALL_KEY"]
        config["aws_s3_landing_bucket"] = os.environ["AWS_S3_LANDING_BUCKET_NAME"]
        # An empty value means "not set": orchestrators pass it unconditionally.
        if delay_override := os.environ.get("API_DELAY_SECONDS"):
            config["api"]["limits"]["delay_seconds"] = float(delay_override)
    except KeyError as e:
        logger.error(f"Missing environment variable: {e}")
        raise

    return config
