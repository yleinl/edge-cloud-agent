# core/scheduler_service.py
"""
Main scheduler service that orchestrates function execution
across different architectures (centralized, federated, decentralized).
"""
import time
import random
import psutil
import requests
from collections import defaultdict, deque
from core.execution_engine import ExecutionEngine
from core.tail_scheduler import TailRatioScheduler
from core.target_selector import TargetSelector

class SchedulerService:
    """Main service for handling scheduling requests across architectures."""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.execution_engine = ExecutionEngine()
        self.tail_scheduler = TailRatioScheduler()
        self.target_selector = TargetSelector()
        
        # Performance tracking
        self.response_log = defaultdict(deque)
        self.total_time_log = defaultdict(deque)
        self.TIME_WINDOW = 60
        self.TOTAL_TIME_WINDOW = 60
        self.alpha = 0.3  # Hop penalty factor
    
    def handle_request(self, data):
        """Handle incoming execution request and route to appropriate architecture."""
        total_start = time.time()
        
        # Extract request parameters
        request_params = self._extract_request_params(data)
        
        # Dynamic architecture selection if needed
        if request_params["arch"] == "dynamic":
            request_params["arch"] = self._select_dynamic_architecture(
                request_params["fn_name"]
            )
        
        try:
            # Route to appropriate architecture handler
            if request_params["arch"] == "centralized":
                result = self._handle_centralized(request_params)
            elif request_params["arch"] == "federated":
                result = self._handle_federated(request_params)
            elif request_params["arch"] == "decentralized":
                result = self._handle_decentralized(request_params)
            else:
                return {
                    "response": {"error": f"Unsupported architecture: {request_params['arch']}"},
                    "status": 400
                }
            
            # Add execution metadata
            result["response"]["total_time"] = round(time.time() - total_start, 6)
            result["response"]["hop"] = request_params["hop"]
            result["response"]["architecture"] = request_params["arch"]
            
            # Record performance metrics
            self._record_total_time(request_params["fn_name"], 
                                  request_params["arch"], 
                                  result["response"]["total_time"])
            
            return result
            
        except Exception as e:
            return {
                "response": {"error": f"Execution failed: {str(e)}"},
                "status": 500
            }
    
    def schedule_function(self, data):
        """Direct function scheduling (used in centralized architecture)."""
        request_params = self._extract_request_params(data)
        
        if request_params["arch"] == "centralized":
            return self._handle_centralized_scheduling(request_params)
        elif request_params["arch"] == "federated":
            return self._handle_federated_scheduling(request_params)
        else:
            return {
                "response": {"error": "Unsupported scheduling architecture"},
                "status": 500
            }
    
    def _extract_request_params(self, data):
        """Extract and validate request parameters."""
        return {
            "tag": data.get("tag", "default"),
            "fn_name": data.get("fn_name", "hello"),
            "payload": data.get("payload", ""),
            "deadline": data.get("deadline", ""),
            "hop": data.get("hop", 0),
            "arch": data.get("arch", self.config_manager.get_architecture())
        }
    
    def _select_dynamic_architecture(self, fn_name):
        """Select architecture dynamically based on performance metrics."""
        durations_dict = {
            "centralized": self._get_recent_total_times(fn_name + "_centralized"),
            "federated": self._get_recent_total_times(fn_name + "_federated"),
            "decentralized": self._get_recent_total_times(fn_name + "_decentralized")
        }
        arch_ratios = self.tail_scheduler.update_ratios(fn_name, durations_dict)
        return self.tail_scheduler.select_arch(arch_ratios)
    
    def _handle_centralized(self, params):
        """Handle request in centralized architecture."""
        self_node = self.config_manager.self_node
        topo = self.config_manager.topo_map
        
        if self_node.get("role") == "cloud-controller":
            # Select target and execute
            available_targets = list(topo.values())
            target = self.target_selector.select_target(
                available_targets, params["fn_name"], self.response_log
            )
            
            start_time = time.time()
            result = self.execution_engine.invoke_remote_faas(
                params["fn_name"], params["payload"], target
            )
            duration = time.time() - start_time
            
            self._record_response_time(target["id"], params["fn_name"], duration)
            return {"response": result, "status": 200}
        else:
            # Forward to centralized scheduler
            return self._forward_to_controller(params, "cloud-controller", "/schedule")
    
    def _handle_federated(self, params):
        """Handle request in federated architecture."""
        self_node = self.config_manager.self_node
        node_role = self_node.get("role")
        node_zone = self_node.get("zone")
        topo = self.config_manager.topo_map
        
        if node_role == "edge-controller":
            return self._handle_federated_edge_controller(params)
        elif node_role == "cloud-controller":
            result = self.execution_engine.invoke_local_faas(
                params["fn_name"], params["payload"]
            )
            return {"response": result, "status": 200}
        else:
            # Forward to edge controller in same zone
            schedulers = [n for n in topo.values() 
                         if n["zone"] == node_zone and n["role"] == "edge-controller"]
            if schedulers:
                controller = schedulers[0]
                return self._forward_to_specific_controller(params, controller, "/entry")
            else:
                return {
                    "response": {"error": "No edge controller in same zone"},
                    "status": 500
                }
    
    def _handle_decentralized(self, params):
        """Handle request in decentralized architecture."""
        self_node = self.config_manager.self_node
        topo = self.config_manager.topo_map
        
        # Decide whether to execute locally or offload
        if params["hop"] >= 2 or psutil.getloadavg()[0] <= 2:
            target = self_node
        else:
            candidates = list(topo.values())
            target = self.target_selector.select_target(
                candidates, params["fn_name"], self.response_log
            )
        
        start_time = time.time()
        
        if target["id"] != self_node["id"]:
            # Offload to another node
            result = self._offload_to_node(params, target)
            duration = time.time() - start_time
            duration *= 1 + self.alpha * result.get("hop", 0)
        else:
            # Execute locally
            result = self.execution_engine.invoke_local_faas(
                params["fn_name"], params["payload"]
            )
            duration = time.time() - start_time
        
        self._record_response_time(target["id"], params["fn_name"], duration)
        return {"response": result, "status": 200}
    
    def _handle_centralized_scheduling(self, params):
        """Handle direct scheduling in centralized architecture."""
        self_node = self.config_manager.self_node
        
        if self_node.get("role") != "cloud-controller":
            return {
                "response": {"error": "Edge nodes cannot initiate scheduling in centralized architecture"},
                "status": 403
            }
        
        # Select target and execute
        topo = self.config_manager.topo_map
        available_targets = list(topo.values())
        target = self.target_selector.select_target(
            available_targets, params["fn_name"], self.response_log
        )
        
        start_time = time.time()
        result = self.execution_engine.invoke_remote_faas(
            params["fn_name"], params["payload"], target
        )
        duration = time.time() - start_time
        
        self._record_response_time(target["id"], params["fn_name"], duration)
        
        return {
            "response": {"resp": result.get("resp")},
            "status": 200
        }
    
    def _handle_federated_scheduling(self, params):
        """Handle direct scheduling in federated architecture."""
        self_node = self.config_manager.self_node
        node_role = self_node.get("role")
        node_zone = self_node.get("zone")
        
        if node_role != "edge-controller":
            return {
                "response": {"error": "Only edge controllers can schedule in federated architecture"},
                "status": 403
            }
        
        # Select targets within the same zone
        topo = self.config_manager.topo_map
        available_targets = [
            n for n in topo.values()
            if n["zone"] == node_zone
        ]
        
        if not available_targets:
            return {
                "response": {"error": "No targets available in current zone"},
                "status": 500
            }
        
        target = self.target_selector.select_target(
            available_targets, params["fn_name"], self.response_log
        )
        
        start_time = time.time()
        result = self.execution_engine.invoke_remote_faas(
            params["fn_name"], params["payload"], target
        )
        duration = time.time() - start_time
        
        self._record_response_time(target["id"], params["fn_name"], duration)
        
        return {
            "response": {"resp": result.get("resp")},
            "status": 200
        }
    
    def _handle_federated_edge_controller(self, params):
        """Handle federated scheduling from edge controller perspective."""
        self_node = self.config_manager.self_node
        node_zone = self_node.get("zone")
        topo = self.config_manager.topo_map
        
        # Decide whether to execute locally or offload
        if params["hop"] >= 2 or psutil.getloadavg()[0] <= 2:
            target = self_node
        else:
            candidates = [n for n in topo.values() 
                         if n["role"] in ("cloud-controller", "edge-controller")]
            target = self.target_selector.select_zone(
                candidates, params["fn_name"], self.response_log
            )
        
        if target["zone"] != node_zone:
            # Offload to another zone
            return self._offload_to_zone(params, target)
        else:
            # Execute in local zone
            return self._execute_in_local_zone(params)
    
    def _offload_to_zone(self, params, target):
        """Offload request to another zone."""
        url = f"http://{target['address']}:31113/entry"
        params["hop"] = params["hop"] + 1
        
        try:
            start_time = time.time()
            response = requests.post(url, json=params, timeout=60)
            duration = time.time() - start_time
            duration *= 1 + self.alpha * response.json().get("hop", 0)
            
            self._record_response_time(target["zone"], params["fn_name"], duration)
            
            return {
                "response": {
                    "message": f"Offloaded to zone {target['zone']}",
                    "response": response.json()
                },
                "status": response.status_code
            }
        except requests.RequestException as e:
            return {"response": {"error": str(e)}, "status": 500}
    
    def _execute_in_local_zone(self, params):
        """Execute function in local zone."""
        self_node = self.config_manager.self_node
        node_zone = self_node.get("zone")
        topo = self.config_manager.topo_map
        
        # Select target within local zone
        schedule_targets = [n for n in topo.values() if n["zone"] == node_zone]
        target = self.target_selector.select_target(
            schedule_targets, params["fn_name"], self.response_log
        )
        
        start_time = time.time()
        result = self.execution_engine.invoke_remote_faas(
            params["fn_name"], params["payload"], target
        )
        duration = time.time() - start_time
        
        self._record_response_time(node_zone, params["fn_name"], duration)
        
        return {"response": result, "status": 200}
    
    def _forward_to_controller(self, params, role_type, endpoint):
        """Forward request to a controller of specified role."""
        topo = self.config_manager.topo_map
        controllers = [n for n in topo.values() if n["role"] == role_type]
        
        if not controllers:
            return {
                "response": {"error": f"No {role_type} found"},
                "status": 500
            }
        
        controller = random.choice(controllers)
        url = f"http://{controller['address']}:31113{endpoint}"
        
        try:
            response = requests.post(url, json=params, timeout=60)
            return {"response": response.json(), "status": response.status_code}
        except requests.RequestException as e:
            return {"response": {"error": str(e)}, "status": 500}
    
    def _forward_to_specific_controller(self, params, controller, endpoint):
        """Forward request to a specific controller."""
        url = f"http://{controller['address']}:31113{endpoint}"
        
        try:
            response = requests.post(url, json=params, timeout=60)
            return {"response": response.json(), "status": response.status_code}
        except requests.RequestException as e:
            return {"response": {"error": str(e)}, "status": 500}
    
    def _offload_to_node(self, params, target):
        """Offload request to another node in decentralized mode."""
        url = f"http://{target['address']}:31113/entry"
        params["hop"] = params["hop"] + 1
        
        try:
            response = requests.post(url, json=params, timeout=60)
            return {
                "message": f"Offloaded to node {target['id']}",
                "response": response.json()
            }
        except requests.RequestException as e:
            return {"error": str(e)}
    
    def _record_response_time(self, node_id, fn_name, duration):
        """Record response time for performance tracking."""
        now = time.time()
        key = (node_id, fn_name)
        self.response_log[key].append((now, duration))
        
        # Clean old entries
        while (self.response_log[key] and 
               now - self.response_log[key][0][0] > self.TIME_WINDOW):
            self.response_log[key].popleft()
    
    def _record_total_time(self, fn_name, arch, total_time):
        """Record total execution time for architecture performance tracking."""
        now = time.time()
        key = f"{fn_name}_{arch}"
        self.total_time_log[key].append((now, total_time))
        
        # Clean old entries
        while (self.total_time_log[key] and 
               now - self.total_time_log[key][0][0] > self.TOTAL_TIME_WINDOW):
            self.total_time_log[key].popleft()
        
        # Record in tail scheduler
        self.tail_scheduler.record_arch_perf(arch, total_time)
    
    def _get_recent_total_times(self, key):
        """Get recent total execution times for a specific function-architecture combination."""
        now = time.time()
        return [duration for ts, duration in self.total_time_log.get(key, []) 
                if now - ts <= self.TOTAL_TIME_WINDOW]
    
    def get_architecture_metrics(self):
        """Get current architecture performance metrics."""
        return self.tail_scheduler.get_metrics()
    
    def get_recent_durations(self):
        """Get recent durations for all architectures."""
        fn_name = "matrix-multiplication"  # Could be parameterized
        return {
            "centralized": self._get_recent_total_times(fn_name + "_centralized"),
            "federated": self._get_recent_total_times(fn_name + "_federated"),
            "decentralized": self._get_recent_total_times(fn_name + "_decentralized")
        }
    
    def update_thresholds(self, data):
        """Update scheduling thresholds."""
        self.tail_scheduler.update_thresholds(
            data.get("soft_d2f", 1.3),
            data.get("hard_d2f", 1.7),
            data.get("soft_f2c", 1.6),
            data.get("hard_f2c", 2.7)
        )