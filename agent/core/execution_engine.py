"""
Execution engine for invoking functions on local and remote FaaS platforms.
Handles the actual function invocation and communication with FaaS gateways.
"""
import requests
from typing import Dict, Any


class ExecutionEngine:
    """Handles function execution on local and remote FaaS platforms."""

    def __init__(self, local_gateway_url="http://127.0.0.1:31112/function"):
        self.local_gateway_url = local_gateway_url
        self.timeout = 60  # Request timeout in seconds

    def invoke_local_faas(self, func_name: str, payload: Any) -> Dict[str, Any]:
        """
        Execute function on local FaaS platform.

        Args:
            func_name: Name of the function to execute
            payload: Function payload/input data

        Returns:
            Dict containing response or error information
        """
        try:
            url = f"{self.local_gateway_url}/{func_name}"
            response = requests.post(url, data=payload, timeout=self.timeout)
            response.raise_for_status()

            return {
                "resp": response.text,
                "status": "success"
            }
        except requests.RequestException as e:
            return {
                "error": f"Local FaaS execution failed: {str(e)}",
                "status": "failed"
            }
        except Exception as e:
            return {
                "error": f"Unexpected error during local execution: {str(e)}",
                "status": "failed"
            }

    def invoke_remote_faas(self, func_name: str, payload: Any, target: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute function on remote FaaS platform.

        Args:
            func_name: Name of the function to execute
            payload: Function payload/input data
            target: Target node information (must contain 'address' key)

        Returns:
            Dict containing response or error information
        """
        try:
            if not target or "address" not in target:
                return {
                    "error": "Invalid target node: missing address",
                    "status": "failed"
                }

            url = f"http://{target['address']}:31112/function/{func_name}"
            response = requests.post(url, data=payload, timeout=self.timeout)
            response.raise_for_status()

            return {
                "resp": response.text,
                "status": "success",
                "execution_location": "remote",
                "target_node": target.get("id", "unknown")
            }
        except requests.RequestException as e:
            return {
                "error": f"Remote FaaS execution to {target} failed: {str(e)}",
                "status": "failed",
                "execution_location": "remote",
                "target_node": target.get("id", "unknown")
            }
        except Exception as e:
            return {
                "error": f"Unexpected error during remote execution: {str(e)}",
                "status": "failed",
                "execution_location": "remote",
                "target_node": target.get("id", "unknown")
            }

    def invoke_remote_scheduler(self, url: str, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send request to remote scheduler.

        Args:
            url: Full URL of the remote scheduler endpoint
            request_data: Complete request data to send

        Returns:
            Dict containing response or error information
        """
        try:
            response = requests.post(url, json=request_data, timeout=self.timeout)
            response.raise_for_status()

            return {
                "response": response.json(),
                "status": response.status_code,
                "execution_location": "remote_scheduler"
            }
        except requests.RequestException as e:
            return {
                "error": f"Remote scheduler call failed: {str(e)}",
                "status": 500,
                "execution_location": "remote_scheduler"
            }
        except Exception as e:
            return {
                "error": f"Unexpected error calling remote scheduler: {str(e)}",
                "status": 500,
                "execution_location": "remote_scheduler"
            }
