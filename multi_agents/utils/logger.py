import logging
import agentops
import os


def setup_logger(use_agentops=False):
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    if use_agentops:
        agentops.init(api_key=os.getenv("AGENTOPS_API_KEY"), default_tags=["dev-run"])
        logger.info("AgentOps initialized and tracking started.")

    return logger
