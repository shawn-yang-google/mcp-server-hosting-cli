"""
Deployment manager for MCP servers.
"""

import os
import subprocess
from typing import Optional, Dict
from google.cloud import run_v2
from google.cloud.run_v2 import Service
from google.api_core import exceptions
import shutil
import logging # Added for logging
import tempfile  # For creating temporary bash script
import json
import git # For cloning git repository

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
                "--quiet", # Suppress output, just check existence via return code
            ], check=True, capture_output=True) # capture_output to check stderr if needed
            logger.info(f"Repository {self.artifact_repository_name} already exists.")
        except subprocess.CalledProcessError as e:
            # More robust check for "NOT_FOUND" or if the command failed to find the repo
            # Some gcloud versions might not have a specific "NOT_FOUND" string but exit with non-zero
            # when describe fails on a non-existent resource.
            # We can inspect stderr for messages hinting at not found, or assume creation is needed if describe fails.
            logger.warning(f"Repository {self.artifact_repository_name} not found or error describing it (stderr: {e.stderr.decode()}). Attempting to create...")
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


    def _run_deploy_script(self, image_name: str, dockerfile_abs_path: str, build_context_abs_path: str, deploy_dir_build_arg: Optional[str] = None) -> None:
        """Run the docker.sh script to handle Docker authentication and deployment.
        
        Args:
            image_name: Full image name to build and push (e.g., REGISTRY_DOMAIN/PROJECT_ID/REPO/IMAGE_ID)
            dockerfile_abs_path: Absolute path to the Dockerfile.
            build_context_abs_path: Absolute path to the build context.
            deploy_dir_build_arg: Optional. Value for the DEPLOY_DIR_ARG build argument.
                                  Used by the root Dockerfile to locate server.py and requirements.txt.
            
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
        command = [
            script_path,
            self.artifact_registry_domain,
            image_name,
            dockerfile_abs_path,
            build_context_abs_path
        ]
        if deploy_dir_build_arg:
            command.append(deploy_dir_build_arg)
        else:
            command.append("") # Pass an empty string if no build arg

        try:
            subprocess.run(command, check=True)
            logger.info("Docker build and push completed successfully.")
        except Exception as e:
            logger.error(f"Docker build and push failed: {str(e)}")
            raise

    def deploy_server(self, name: str, server_file: str, container_port: int = 8080, startup_probe_path: Optional[str] = None) -> str:
        """Deploy a server to Cloud Run (original workflow).
        
        Args:
            name: Server name
            server_file: Path to server file (e.g., servers/my-server.py)
            container_port: The port the application inside the container will listen on.
                            Cloud Run will set the PORT env var to this value.
            startup_probe_path: Optional. The HTTP path for the startup probe. Defaults to '/'.
            
        Returns:
            The deployed service URL
            
        Raises:
            FileNotFoundError: If server file or requirements.txt doesn't exist
            subprocess.CalledProcessError: If deployment command fails
        """
        deploy_dir_relative_to_project_root = f"deploy/{name}" # e.g., "deploy/my-server"
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")) # Assumes backend is mcp_host/backend/
        
        try:
            self._ensure_artifact_repository_exists()

            # Create clean temporary directory for deployment (relative to project root for Docker context)
            full_deploy_dir_path = os.path.join(project_root, deploy_dir_relative_to_project_root)
            if os.path.exists(full_deploy_dir_path):
                shutil.rmtree(full_deploy_dir_path)
            os.makedirs(full_deploy_dir_path, exist_ok=True)
            
            # Copy server file (e.g., servers/my-server.py to deploy/my-server/server.py)
            if not os.path.exists(server_file): # server_file is likely relative to project root already e.g. "servers/my-server.py"
                raise FileNotFoundError(f"Server file {server_file} not found")
                
            with open(server_file, "r") as src, open(os.path.join(full_deploy_dir_path, "server.py"), "w") as dst:
                dst.write(src.read())
            
            # Copy requirements.txt from project root to deploy_dir/requirements.txt
            project_requirements_path = os.path.join(project_root, "requirements.txt")
            if not os.path.exists(project_requirements_path):
                raise FileNotFoundError(f"{project_requirements_path} not found in project root. This is needed for the Docker build.")
            shutil.copy(project_requirements_path, os.path.join(full_deploy_dir_path, "requirements.txt"))
            logger.info(f"Copied {project_requirements_path} to {full_deploy_dir_path}")

            # The Dockerfile used for this workflow is the one at the project root.
            project_dockerfile_path = os.path.join(project_root, "Dockerfile")
            if not os.path.exists(project_dockerfile_path):
                raise FileNotFoundError(f"{project_dockerfile_path} not found in project root. Please create one.")
            # No need to copy it to deploy_dir, docker.sh will reference it directly.
            
            image_name = f"{self.artifact_registry_domain}/{self.project_id}/{self.artifact_repository_name}/{name}"
            logger.info(f"Building and pushing image for standard server: {image_name}")
            
            # For this original workflow, the build context is the project root.
            # The DEPLOY_DIR_ARG tells the root Dockerfile where to find server.py and requirements.txt
            # which were copied into the temporary deploy_dir_relative_to_project_root.
            self._run_deploy_script(
                image_name=image_name,
                dockerfile_abs_path=project_dockerfile_path,
                build_context_abs_path=project_root,
                deploy_dir_build_arg=deploy_dir_relative_to_project_root # e.g. "deploy/my-server"
            )
            
            service_name_for_run_cli = name 
            logger.info(f"Deploying service {service_name_for_run_cli} to Cloud Run using container.sh with image {image_name} on port {container_port}")

            container_script_path = os.path.join(os.path.dirname(__file__), "container.sh")

            if not os.access(container_script_path, os.X_OK):
                os.chmod(container_script_path, 0o755)
            
            try:
                subprocess.run([
                    container_script_path,
                    service_name_for_run_cli,
                    image_name,
                    self.project_id,
                    self.region,
                    str(container_port), # Pass container_port to container.sh
                    "1",  # Default CPU for container.sh
                    "512Mi",  # Default Memory for container.sh
                    startup_probe_path if startup_probe_path is not None else "" # Pass startup_probe_path or empty string
                ], check=True, capture_output=True)
                logger.info(f"Cloud Run deployment script for service {name} executed successfully.")
            except subprocess.CalledProcessError as e:
                logger.error(f"Cloud Run deployment script failed for service {name}: {e.stderr.decode()}")
                raise

            service_url = self.get_service_url(name)
            if not service_url:
                 raise Exception(f"Failed to get service URL for {name} after deployment.")
            return service_url
            
        except Exception as e:
            logger.error(f"Deployment failed for server '{name}': {str(e)}")
            # Clean up on failure
            if 'full_deploy_dir_path' in locals() and os.path.exists(full_deploy_dir_path):
                shutil.rmtree(full_deploy_dir_path)
            raise e

    def deploy_git_repository(self, service_name: str, git_repo_url: str, dockerfile_path_in_repo: str = "Dockerfile", container_port: int = 8080, startup_probe_path: Optional[str] = None, env_vars: Optional[Dict[str, str]] = None) -> str:
        """Clones a Git repository and deploys it as a Cloud Run service using its Dockerfile.

        Args:
            service_name: The name for the Cloud Run service.
            git_repo_url: The URL of the Git repository.
            dockerfile_path_in_repo: Relative path to the Dockerfile within the repository. Defaults to "Dockerfile".
            container_port: The port the application inside the container is expected to listen on.
                            Cloud Run will set the PORT env var to this value. User's app must honor this.
            startup_probe_path: Optional. The HTTP path for the startup probe. Defaults to '/'.
            env_vars: Optional. A dictionary of environment variables to set in the container.

        Returns:
            The deployed service URL.

        Raises:
            Exception: If any step of the cloning, building, or deployment process fails.
        """
        temp_clone_dir = tempfile.mkdtemp(prefix=f"mcp_deploy_git_{service_name}_")
        logger.info(f"Cloning repository {git_repo_url} into {temp_clone_dir}")

        try:
            self._ensure_artifact_repository_exists()
            
            # Clone the repository
            try:
                git.Repo.clone_from(git_repo_url, temp_clone_dir)
                logger.info(f"Successfully cloned repository to {temp_clone_dir}")
            except git.GitCommandError as e:
                logger.error(f"Failed to clone repository {git_repo_url}: {e.stderr}")
                raise Exception(f"Git clone failed: {e.stderr}") from e

            # Determine paths
            build_context_abs_path = temp_clone_dir
            dockerfile_abs_path = os.path.join(build_context_abs_path, dockerfile_path_in_repo)

            if not os.path.isfile(dockerfile_abs_path):
                raise FileNotFoundError(f"Dockerfile not found at {dockerfile_abs_path} in the cloned repository.")

            image_name = f"{self.artifact_registry_domain}/{self.project_id}/{self.artifact_repository_name}/{service_name}"
            logger.info(f"Building and pushing image for Git repo: {image_name}")

            # Build and push the Docker image from the cloned repo.
            # No DEPLOY_DIR_ARG is needed here as the repo's Dockerfile should be self-sufficient.
            self._run_deploy_script(
                image_name=image_name,
                dockerfile_abs_path=dockerfile_abs_path,
                build_context_abs_path=build_context_abs_path,
                deploy_dir_build_arg=None # User's Dockerfile is self-contained
            )

            # Deploy to Cloud Run using container.sh
            logger.info(f"Deploying service {service_name} to Cloud Run using container.sh with image {image_name} on port {container_port}")
            container_script_path = os.path.join(os.path.dirname(__file__), "container.sh")
            if not os.access(container_script_path, os.X_OK):
                os.chmod(container_script_path, 0o755)

            env_vars_string = ""
            if env_vars:
                env_vars_string = ",".join([f"{k}={v}" for k, v in env_vars.items()])

            try:
                subprocess.run([
                    container_script_path,
                    service_name,
                    image_name,
                    self.project_id,
                    self.region,
                    str(container_port),
                    "1",  # Default CPU
                    "512Mi",  # Default Memory
                    startup_probe_path if startup_probe_path is not None else "",
                    env_vars_string # Pass formatted env vars string
                ], check=True, capture_output=True)
                logger.info(f"Cloud Run deployment script for service {service_name} executed successfully.")
            except subprocess.CalledProcessError as e:
                logger.error(f"Cloud Run deployment script failed for service {service_name}: {e.stderr.decode()}")
                raise

            service_url = self.get_service_url(service_name)
            if not service_url:
                raise Exception(f"Failed to get service URL for {service_name} after git repo deployment.")
            return service_url

        except Exception as e:
            logger.error(f"Deployment of Git repository {git_repo_url} as service '{service_name}' failed: {str(e)}")
            raise
        finally:
            # Clean up the temporary clone directory
            if os.path.exists(temp_clone_dir):
                shutil.rmtree(temp_clone_dir)
                logger.info(f"Cleaned up temporary clone directory: {temp_clone_dir}")


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
                     logger.error(f"Permission error deleting service '{name}' with gcloud: {result.stderr.strip()}")
                     # Optionally, re-raise an exception here if you want the CLI to stop more forcefully
                     # raise Exception(f"gcloud permission error: {result.stderr.strip()}")
                elif "not found" not in result.stderr.lower(): # If not a 'not found' error (which --quiet should handle)
                     logger.warning(f"gcloud command to delete service '{name}' exited with code {result.returncode}. Stderr: {result.stderr.strip()}")
                # else: service not found, --quiet handles this, proceed with local cleanup
            else:
                logger.info(f"Cloud Run service '{name}' deleted successfully or was already gone.")

        except FileNotFoundError:
            logger.error("Error: gcloud command not found. Please ensure it's installed and in your PATH.")
            # Potentially raise an exception here if gcloud is essential and its absence should stop the process
            # raise
        except Exception as e:
            # Catch any other unexpected errors during the gcloud call itself
            logger.error(f"An unexpected error occurred while trying to delete service '{name}' via gcloud: {e}")
            # raise # Optionally re-raise

        # Proceed with local file and directory cleanup regardless of remote deletion status, 
        # as the goal is to remove the server configuration from the local environment as well.
        try:
            deploy_dir = f"deploy/{name}"
            if os.path.exists(deploy_dir):
                shutil.rmtree(deploy_dir)
                logger.info(f"Removed local deployment directory: {deploy_dir}")
            
            if delete_local_file:
                local_server_file = f"servers/{name}.py"
                if os.path.exists(local_server_file):
                    os.remove(local_server_file)
                    logger.info(f"Removed local server file: {local_server_file}")
                elif not os.path.exists(local_server_file) and not result.returncode == 0 and "not found" in result.stderr.lower():
                    # If local file was already gone and remote service also not found.
                    pass # No specific message needed if both were already gone.
                elif not os.path.exists(local_server_file):
                     logger.info(f"Local server file {local_server_file} not found, no local file to remove.")

        except Exception as e:
            logger.error(f"Error during local file cleanup for server '{name}': {e}")

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
            logger.error(f"Error parsing JSON from gcloud services list: {e}")
            return [] 