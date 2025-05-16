"""
Deployment manager for MCP servers.
"""

import os
import subprocess
from typing import Optional
from google.cloud import run_v2
from google.cloud.run_v2 import Service
from google.api_core import exceptions
import shutil
import logging # Added for logging
import tempfile  # For creating temporary bash script
import json

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DeploymentManager:
    """Manages deployment of MCP servers to Cloud Run."""

    def __init__(self, project_id: str, region: str):
        """Initialize the deployment manager.
        
        Args:
            project_id: GCP project ID
            region: GCP region
        """
        self.project_id = project_id
        self.region = region
        self.client = run_v2.ServicesClient()
        self.artifact_repository_name = "mcp-server-images"  # Standard repo name
        self.artifact_registry_domain = f"{self.region}-docker.pkg.dev"

    def _ensure_artifact_repository_exists(self):
        """Checks if the Artifact Registry repository exists, and creates it if not."""
        repo_path = f"projects/{self.project_id}/locations/{self.region}/repositories/{self.artifact_repository_name}"
        try:
            # Check if repository exists
            logger.info(f"Checking if Artifact Registry repository {repo_path} exists...")
            subprocess.run([
                "gcloud", "artifacts", "repositories", "describe", self.artifact_repository_name,
                "--project", self.project_id,
                "--location", self.region,
            ], check=True, capture_output=True)
            logger.info(f"Repository {self.artifact_repository_name} already exists.")
        except subprocess.CalledProcessError as e:
            if "NOT_FOUND" in e.stderr.decode(): # Check if error is because repo not found
                logger.info(f"Repository {self.artifact_repository_name} not found. Creating...")
                try:
                    subprocess.run([
                        "gcloud", "artifacts", "repositories", "create", self.artifact_repository_name,
                        "--project", self.project_id,
                        "--location", self.region,
                        "--repository-format", "docker",
                        "--description", "Repository for MCP server images"
                    ], check=True, capture_output=True)
                    logger.info(f"Successfully created Artifact Registry repository: {self.artifact_repository_name}")
                except subprocess.CalledProcessError as create_e:
                    logger.error(f"Failed to create Artifact Registry repository: {create_e.stderr.decode()}")
                    raise  # Re-raise the exception if creation fails
            else:
                # Some other error occurred during describe
                logger.error(f"Error checking repository: {e.stderr.decode()}")
                raise


    def _run_deploy_script(self, deploy_dir: str, image: str) -> None:
        """Run the docker.sh script to handle Docker authentication and deployment.
        
        Args:
            deploy_dir: Directory containing deployment files
            image: Full image name to build and push
            
        Raises:
            subprocess.CalledProcessError: If the script execution fails
        """
        # Get the path to the docker.sh script (in the same directory as this file)
        script_path = os.path.join(os.path.dirname(__file__), "docker.sh")
        
        # Make sure the script is executable
        if not os.access(script_path, os.X_OK):
            os.chmod(script_path, 0o755)
        
        # Run the script with the required parameters
        logger.info(f"Running Docker build and push using {script_path}...")
        try:
            subprocess.run([
                script_path,
                self.artifact_registry_domain,
                image,
                deploy_dir
            ], check=True)
            logger.info("Docker build and push completed successfully.")
        except Exception as e:
            logger.error(f"Docker build and push failed: {str(e)}")
            raise

    def deploy_server(self, name: str, server_file: str) -> str:
        """Deploy a server to Cloud Run.
        
        Args:
            name: Server name
            server_file: Path to server file
            
        Returns:
            The deployed service URL
            
        Raises:
            FileNotFoundError: If server file or requirements.txt doesn't exist
            subprocess.CalledProcessError: If deployment command fails
        """
        deploy_dir = f"deploy/{name}"
        
        try:
            # Ensure Artifact Registry repository exists or create it
            self._ensure_artifact_repository_exists()

            # Create clean temporary directory for deployment
            if os.path.exists(deploy_dir):
                shutil.rmtree(deploy_dir)
            os.makedirs(deploy_dir, exist_ok=True)
            
            # Copy server file
            if not os.path.exists(server_file):
                raise FileNotFoundError(f"Server file {server_file} not found")
                
            with open(server_file, "r") as src, open(f"{deploy_dir}/server.py", "w") as dst:
                dst.write(src.read())
            
            # Copy requirements.txt from project root
            project_requirements_path = "requirements.txt"
            if not os.path.exists(project_requirements_path):
                raise FileNotFoundError(f"{project_requirements_path} not found in project root. This is needed for the Docker build.")
            shutil.copy(project_requirements_path, f"{deploy_dir}/requirements.txt")
            logger.info(f"Copied {project_requirements_path} to {deploy_dir}")

            # Copy Dockerfile from project root
            project_dockerfile_path = "Dockerfile"
            if not os.path.exists(project_dockerfile_path):
                raise FileNotFoundError(f"{project_dockerfile_path} not found in project root. Please create one.")
            shutil.copy(project_dockerfile_path, f"{deploy_dir}/Dockerfile")
            logger.info(f"Copied {project_dockerfile_path} to {deploy_dir}")
            
            # Build and push container to Artifact Registry
            image = f"{self.artifact_registry_domain}/{self.project_id}/{self.artifact_repository_name}/{name}"
            logger.info(f"Building and pushing image: {image}")
            
            # Use the new script-based approach instead of gcloud builds submit
            self._run_deploy_script(deploy_dir, image)
            
            # Deploy to Cloud Run using the container.sh script
            service_name_for_run_cli = name # For gcloud CLI, service_id is just the name
            logger.info(f"Deploying service {service_name_for_run_cli} to Cloud Run using container.sh with image {image}")

            container_script_path = os.path.join(os.path.dirname(__file__), "container.sh")

            # Make sure the script is executable
            if not os.access(container_script_path, os.X_OK):
                os.chmod(container_script_path, 0o755)
            
            try:
                subprocess.run([
                    container_script_path,
                    service_name_for_run_cli,
                    image,
                    self.project_id,
                    self.region
                    # Optionally, pass port, CPU, memory if different from script defaults
                    # "8080", 
                    # "1", 
                    # "512Mi" 
                ], check=True, capture_output=True) # Capture output to see logs from script
                logger.info(f"Cloud Run deployment script for service {name} executed successfully.")
            except subprocess.CalledProcessError as e:
                logger.error(f"Cloud Run deployment script failed for service {name}: {e.stderr.decode()}")
                raise

            # Get the service URL
            service_url = self.get_service_url(name)
            return service_url
            
        except Exception as e:
            logger.error(f"Deployment failed: {str(e)}")
            # Clean up on failure
            if os.path.exists(deploy_dir):
                shutil.rmtree(deploy_dir)
            raise e

    def delete_server(self, name: str, delete_local_file: bool = True):
        """Delete a Cloud Run service using gcloud and optionally its local configuration file."""
        logger.info(f"Attempting to delete Cloud Run service '{name}' using gcloud...")
        try:
            command = [
                "gcloud", "run", "services", "delete", name,
                "--platform", "managed",
                "--region", self.region,
                "--project", self.project_id,
                "--quiet"  # Suppress prompts, and doesn't error if service not found
            ]
            result = subprocess.run(command, check=False, capture_output=True, text=True) # check=False as --quiet handles not found

            if result.returncode != 0:
                # Log gcloud error, but don't necessarily stop local cleanup if it was a non-critical issue like service not found (handled by --quiet)
                # However, if it's a permission error, we should log it prominently.
                # The error message you saw (403 Permission denied) will be in stderr.
                if "denied" in result.stderr.lower() or "permission" in result.stderr.lower():
                     logger.error(f"Permission error deleting service '{name}' with gcloud: {{result.stderr.strip()}}")
                     # Optionally, re-raise an exception here if you want the CLI to stop more forcefully
                     # raise Exception(f"gcloud permission error: {{result.stderr.strip()}}")
                elif "not found" not in result.stderr.lower(): # If not a 'not found' error (which --quiet should handle)
                     logger.warning(f"gcloud command to delete service '{name}' exited with code {{result.returncode}}. Stderr: {{result.stderr.strip()}}")
                # else: service not found, --quiet handles this, proceed with local cleanup
            else:
                logger.info(f"Cloud Run service '{name}' deleted successfully or was already gone.")

        except FileNotFoundError:
            logger.error("Error: gcloud command not found. Please ensure it's installed and in your PATH.")
            # Potentially raise an exception here if gcloud is essential and its absence should stop the process
            # raise
        except Exception as e:
            # Catch any other unexpected errors during the gcloud call itself
            logger.error(f"An unexpected error occurred while trying to delete service '{name}' via gcloud: {{e}}")
            # raise # Optionally re-raise

        # Proceed with local file and directory cleanup regardless of remote deletion status, 
        # as the goal is to remove the server configuration from the local environment as well.
        try:
            deploy_dir = f"deploy/{{name}}"
            if os.path.exists(deploy_dir):
                shutil.rmtree(deploy_dir)
                logger.info(f"Removed local deployment directory: {{deploy_dir}}")
            
            if delete_local_file:
                local_server_file = f"servers/{{name}}.py"
                if os.path.exists(local_server_file):
                    os.remove(local_server_file)
                    logger.info(f"Removed local server file: {{local_server_file}}")
                elif not os.path.exists(local_server_file) and not result.returncode == 0 and "not found" in result.stderr.lower():
                    # If local file was already gone and remote service also not found.
                    pass # No specific message needed if both were already gone.
                elif not os.path.exists(local_server_file):
                     logger.info(f"Local server file {{local_server_file}} not found, no local file to remove.")

        except Exception as e:
            logger.error(f"Error during local file cleanup for server '{name}': {{e}}")

    def get_service_url(self, name: str) -> Optional[str]:
        """Get the URL of a deployed Cloud Run service using gcloud.
        
        Args:
            name: Server name
            
        Returns:
            The service URL if deployed, None otherwise
        """
        try:
            command = [
                "gcloud", "run", "services", "describe", name,
                "--platform", "managed",
                "--region", self.region,
                "--project", self.project_id,
                "--format", "value(status.url)"
            ]
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            url = result.stdout.strip()
            return url if url else None
        except subprocess.CalledProcessError as e:
            # Handle case where service is not found or other gcloud errors
            print(f"Error getting service URL for '{name}' via gcloud: {e}")
            print(f"gcloud stderr: {e.stderr}")
            return None
        except FileNotFoundError:
            print("Error: gcloud command not found. Please ensure it's installed and in your PATH.")
            return None

    def list_deployed_services(self) -> list[dict]:
        """List all deployed Cloud Run services in the configured project and region using gcloud."""
        try:
            command = [
                "gcloud", "run", "services", "list",
                "--platform", "managed",
                "--region", self.region,
                "--project", self.project_id,
                "--format", "json"
            ]
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            services_data = json.loads(result.stdout)
            
            services_info = []
            for service in services_data:
                service_name = service.get("metadata", {}).get("name")
                service_url = service.get("status", {}).get("url")
                if service_name and service_url:
                    services_info.append({"name": service_name, "url": service_url, "status": "Running"})
            return services_info
        except subprocess.CalledProcessError as e:
            logger.error(f"Error listing services via gcloud: {e.stderr.decode()}")
            return []
        except FileNotFoundError:
            logger.error("Error: gcloud command not found. Please ensure it's installed and in your PATH.")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON from gcloud services list: {{e}}")
            return [] 