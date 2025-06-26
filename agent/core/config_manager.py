"""
Configuration management for FaaS scheduler.
Handles loading and managing architecture configurations and topology information.
"""
import yaml
from typing import Dict, Any, Optional


class ConfigManager:
    """Manages configuration loading and architecture settings."""

    def __init__(self, path: str = "arch/architecture.yaml"):
        self.path = path
        self.config: Dict[str, Any] = {}
        self.self_node: Dict[str, Any] = {}
        self.topo_map: Dict[str, Dict[str, Any]] = {}
        self.arch: str = "centralized"  # Default architecture

        self.load_config()

    def load_config(self):
        """Load configuration from YAML file."""
        try:
            with open(self.path, "r") as f:
                self.config = yaml.safe_load(f)

            # Extract architecture setting
            self.arch = self.config.get("architecture", "centralized")

            # Find self node in topology
            self.self_node = self._find_self_node()

            # Build topology map for quick lookups
            self.topo_map = {
                node["id"]: node
                for node in self.config.get("topology", [])
            }

        except FileNotFoundError:
            raise RuntimeError(f"Configuration file not found: {self.path}")
        except yaml.YAMLError as e:
            raise RuntimeError(f"Error parsing YAML configuration: {e}")
        except Exception as e:
            raise RuntimeError(f"Error loading configuration: {e}")

    def _find_self_node(self) -> Dict[str, Any]:
        """Find current node information in topology."""
        node_config = self.config.get("node", {})
        node_id = node_config.get("id")

        if not node_id:
            raise RuntimeError("Node ID not specified in configuration")

        # Search for node in topology
        for node in self.config.get("topology", []):
            if node["id"] == node_id:
                return node

        raise RuntimeError(f"Node ID '{node_id}' not found in topology configuration")

    def set_architecture(self, arch_name: str):
        """
        Set current architecture.

        Args:
            arch_name: Architecture name (centralized, federated, decentralized, dynamic)
        """
        valid_architectures = ["centralized", "federated", "decentralized", "dynamic"]

        if arch_name not in valid_architectures:
            raise ValueError(f"Invalid architecture: {arch_name}. Must be one of {valid_architectures}")

        self.arch = arch_name

    def get_architecture(self) -> str:
        """Get current architecture setting."""
        return self.arch

    def get_nodes_by_role(self, role: str) -> list:
        """Get all nodes with specified role."""
        return [node for node in self.topo_map.values() if node.get("role") == role]

    def get_nodes_by_zone(self, zone: str) -> list:
        """Get all nodes in specified zone."""
        return [node for node in self.topo_map.values() if node.get("zone") == zone]

    def get_node_by_id(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get node information by ID."""
        return self.topo_map.get(node_id)

    def reload_config(self):
        """Reload configuration from file."""
        self.load_config()

    def validate_config(self) -> bool:
        """
        Validate configuration completeness and correctness.

        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            # Check required fields
            required_fields = ["architecture", "node", "topology"]
            for field in required_fields:
                if field not in self.config:
                    return False

            # Check node configuration
            if "id" not in self.config["node"]:
                return False

            # Check topology
            if not isinstance(self.config["topology"], list):
                return False

            # Check each node in topology has required fields
            required_node_fields = ["id", "address", "role", "zone"]
            for node in self.config["topology"]:
                for field in required_node_fields:
                    if field not in node:
                        return False

            return True

        except Exception:
            return False