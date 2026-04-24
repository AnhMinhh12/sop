import yaml
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ConfigLoader:
    """
    Utility to load and parse YAML configuration files.
    """
    CONFIG_PATH = "config/config.yaml"

    @staticmethod
    def load_config() -> Dict[str, Any]:
        """
        Loads the main configuration file.
        """
        if not os.path.exists(ConfigLoader.CONFIG_PATH):
            logger.error(f"Config file not found at {ConfigLoader.CONFIG_PATH}")
            return {}

        try:
            with open(ConfigLoader.CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                logger.info("Configuration loaded successfully.")
                return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}

    @staticmethod
    def load_sop_definition(station_id: str) -> Dict[str, Any]:
        """
        Loads the SOP steps definition for a specific station.
        """
        sop_path = f"config/sop_definitions/station_{station_id}.yaml"
        if not os.path.exists(sop_path):
            logger.warning(f"SOP definition for station {station_id} not found at {sop_path}. Using empty.")
            return {"station_id": station_id, "steps": []}

        try:
            with open(sop_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load SOP definition for {station_id}: {e}")
            return {"station_id": station_id, "steps": []}
