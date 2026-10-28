"""Project-owned public UI entry point for the contract-compatible Gradio client."""
from __future__ import annotations

import os

from simulator.ui.app_ui import demo


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.getenv("UI_PORT", "7860")),
    )
