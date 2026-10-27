"""Test configuration: keep the suite offline and deterministic."""

import os

# Never call Azure from the automated suite, even if a local .env has credentials.
os.environ["INGAME_LLM"] = "off"
os.environ["INGAME_COSMOS"] = "off"
