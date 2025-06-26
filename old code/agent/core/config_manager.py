import yaml


class ConfigManager:
    def __init__(self, path="arch/architecture.yaml"):
        self.path = path
        self.config = {}
        self.self_node = {}
        self.topo_map = {}
        self.arch = "centralized"  # default

        self.load()

    def load(self):
        with open(self.path, "r") as f:
            self.config = yaml.safe_load(f)

        self.arch = self.config.get("architecture", "centralized")
        self.self_node = self._find_self()
        self.topo_map = {n["id"]: n for n in self.config["topology"]}

    def _find_self(self):
        node_id = self.config["node"]["id"]
        for node in self.config["topology"]:
            if node["id"] == node_id:
                return node
        raise RuntimeError(f"Node ID {node_id} not found in topology")

    def set_architecture(self, arch_name):
        self.arch = arch_name

    def get_architecture(self):
        return self.arch
