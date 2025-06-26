"""
Main entry point for the FaaS scheduler application.
Handles Flask app initialization and command line arguments.
"""
import argparse
from flask import Flask
from core.config_manager import ConfigManager
from api.routes import register_routes


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    return app


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="FaaS Dynamic Scheduler")
    parser.add_argument("--config",
                        default="arch/architecture.yaml",
                        help="Path to architecture configuration file")
    args = parser.parse_args()

    # Initialize configuration manager
    config_manager = ConfigManager(path=args.config)

    # Create Flask app and register routes
    app = create_app()
    register_routes(app, config_manager)

    # Start the application
    app.run(host="0.0.0.0", port=31113, debug=False)


if __name__ == "__main__":
    main()