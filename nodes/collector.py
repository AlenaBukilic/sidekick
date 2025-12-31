from typing import Dict, Any
import sys
from pathlib import Path
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
from state import State


def create_collector_node():
    """Creates a collector node function"""
    def collector(state: State) -> Dict[str, Any]:
        """Aggregates results from parallel workers (deferred execution)"""
        return {}
    
    return collector

