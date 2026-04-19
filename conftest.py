# conftest.py — adds project root to sys.path so pytest can import cell_diff_sim
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
