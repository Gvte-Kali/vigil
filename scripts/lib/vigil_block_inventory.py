"""Run the Core inventory from the isolated legacy shell adapters."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "vigil"))
from block_inventory import mount_inventory

if __name__ == "__main__":
    mount_inventory()
