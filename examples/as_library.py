"""Use miniodk as a library instead of a CLI.

    python examples/as_library.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import miniodk  # noqa: E402

# Optionally force one brain:
#   miniodk.DS_KEY = ""                     -> local Ollama
#   miniodk.LOCAL_MODEL = "llama3.2"        -> another local model
miniodk.MAX_STEPS = 6

answer = miniodk.run("list the files in this folder and tell me the largest one")
print("\nANSWER:", answer)
