import os
import sys

os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("WORKER_ENABLED", "false")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))