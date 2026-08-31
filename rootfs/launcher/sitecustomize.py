"""Automatically install MintKit's framebuffer bridge in child apps."""

import os

if os.environ.get("MINTKIT_CHILD_APP") == "1":
    import mintfb
