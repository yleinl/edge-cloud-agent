"""
Flask route handlers for the FaaS scheduler API.
Contains all HTTP endpoints and request/response handling.
"""
import time
import psutil
from flask import request, jsonify
from core.scheduler_service import SchedulerService
from core.metrics_collector import MetricsCollector


def register_routes(app, config_manager):
    """Register all API routes with the Flask app."""

    # Initialize services
    scheduler_service = SchedulerService(config_manager)
    metrics_collector = MetricsCollector()

    @app.route("/entry", methods=["POST"])
    def entry():
        """Main entry point for function execution requests."""
        try:
            data = request.get_json()
            if "arch" not in data:
                data["arch"] = config_manager.get_architecture()
            result = scheduler_service.handle_request(data)
            return jsonify(result["response"]), result["status"]
        except Exception as e:
            return jsonify({"error": f"Request failed: {str(e)}"}), 500

    @app.route("/schedule", methods=["POST"])
    def schedule():
        """Direct scheduling endpoint for centralized architecture."""
        try:
            data = request.get_json()
            result = scheduler_service.schedule_function(data)
            return jsonify(result["response"]), result["status"]
        except Exception as e:
            return jsonify({"error": f"Scheduling failed: {str(e)}"}), 500

    @app.route("/reload", methods=["POST"])
    def reload_config():
        """Reload architecture configuration."""
        try:
            data = request.get_json()
            new_arch = data.get("architecture")
            if not new_arch:
                return jsonify({"error": "Missing architecture field"}), 400

            config_manager.set_architecture(new_arch)
            return jsonify({
                "message": f"Architecture switched to: {new_arch}",
                "current_arch": config_manager.get_architecture()
            }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/load", methods=["GET"])
    def get_load():
        """Get current node load metrics."""
        try:
            load_info = metrics_collector.get_system_load()
            return jsonify(load_info), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/arch_metrics", methods=["GET"])
    def get_arch_metrics():
        """Get architecture performance metrics."""
        try:
            metrics = scheduler_service.get_architecture_metrics()
            return jsonify(metrics), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/durations", methods=["GET"])
    def get_durations():
        """Get recent execution durations for all architectures."""
        try:
            durations = scheduler_service.get_recent_durations()
            return jsonify(durations), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/update_threshold", methods=["POST"])
    def update_threshold():
        """Update scheduling thresholds."""
        try:
            data = request.get_json()
            scheduler_service.update_thresholds(data)
            return jsonify({"message": "Thresholds updated"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/configuration", methods=["GET"])
    def get_configuration():
        """Get current configuration (for debugging)."""
        try:
            config_info = {
                "arch": config_manager.get_architecture(),
                "self": config_manager.self_node,
                "topology": config_manager.topo_map
            }
            return jsonify(config_info), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
