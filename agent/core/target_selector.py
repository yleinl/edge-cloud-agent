"""
Target selection algorithms for choosing optimal execution nodes.
Implements weighted selection based on historical performance metrics.
"""
import random
import time
from math import prod
from typing import List, Dict, Any
from collections import defaultdict, deque


class TargetSelector:
    """Implements intelligent target selection algorithms."""

    def __init__(self, time_window=60):
        self.time_window = time_window

    def select_target(self, candidates: List[Dict[str, Any]],
                      fn_name: str,
                      response_log: Dict) -> Dict[str, Any]:
        """
        Select optimal target node based on weighted response time distribution.

        Args:
            candidates: List of candidate nodes
            fn_name: Function name for performance lookup
            response_log: Historical response time data

        Returns:
            Selected target node
        """
        if not candidates:
            raise ValueError("No candidates available for selection")

        if len(candidates) == 1:
            return candidates[0]

        # Calculate weighted response times for each candidate
        wrt_list = []
        for node in candidates:
            node_id = node["id"]
            avg_response_time = self._get_average_response_time(
                node_id, fn_name, response_log
            )
            wrt_list.append((node, avg_response_time))

        # Use weighted probability distribution for selection
        selected_node = self._weighted_selection(wrt_list, candidates)
        return selected_node

    def select_zone(self, candidates: List[Dict[str, Any]],
                    fn_name: str,
                    response_log: Dict) -> Dict[str, Any]:
        """
        Select optimal zone based on weighted response time distribution.

        Args:
            candidates: List of candidate nodes with zone information
            fn_name: Function name for performance lookup
            response_log: Historical response time data

        Returns:
            Selected node representing the chosen zone
        """
        if not candidates:
            raise ValueError("No zone candidates available for selection")

        if len(candidates) == 1:
            return candidates[0]

        # Calculate weighted response times for each zone
        wrt_list = []
        for node in candidates:
            zone = node["zone"]
            avg_response_time = self._get_average_response_time(
                zone, fn_name, response_log
            )
            wrt_list.append((node, avg_response_time))

        # Use weighted probability distribution for selection
        selected_node = self._weighted_selection(wrt_list, candidates)
        return selected_node

    def select_random(self, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Random selection fallback method.

        Args:
            candidates: List of candidate nodes

        Returns:
            Randomly selected node
        """
        if not candidates:
            raise ValueError("No candidates available for random selection")

        return random.choice(candidates)

    def _get_average_response_time(self, identifier: str,
                                   fn_name: str,
                                   response_log: Dict) -> float:
        """
        Calculate average response time for a node/zone and function combination.

        Args:
            identifier: Node ID or zone identifier
            fn_name: Function name
            response_log: Historical response time data

        Returns:
            Average response time (0.0 if no data available)
        """
        now = time.time()
        key = (identifier, fn_name)

        # Filter recent response times within the time window
        recent_times = [
            response_time for timestamp, response_time in response_log.get(key, [])
            if now - timestamp <= self.time_window
        ]

        if not recent_times:
            return 0.0  # No historical data available

        return sum(recent_times) / len(recent_times)

    def _weighted_selection(self, wrt_list: List[tuple],
                            candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Perform weighted selection based on inverse response time probability.

        Args:
            wrt_list: List of (node, weight) tuples
            candidates: Original list of candidates (fallback)

        Returns:
            Selected node based on weighted probability
        """
        try:
            # Calculate probability weights using product of other weights
            numerators = []
            for k in range(len(wrt_list)):
                # Calculate product of all other weights (inverse probability)
                left_product = prod([w for _, w in wrt_list[:k]]) if k > 0 else 1
                right_product = prod([w for _, w in wrt_list[k + 1:]]) if k < len(wrt_list) - 1 else 1
                numerators.append(left_product * right_product)

            denominator = sum(numerators)

            # Fallback to random selection if calculation fails
            if denominator == 0 or any(n < 0 for n in numerators):
                return random.choice(candidates)

            # Calculate probabilities and perform weighted selection
            probabilities = [n / denominator for n in numerators]
            selected_index = random.choices(
                range(len(candidates)),
                weights=probabilities,
                k=1
            )[0]

            return wrt_list[selected_index][0]

        except (ValueError, ZeroDivisionError, IndexError):
            # Fallback to random selection on any calculation error
            return random.choice(candidates)