#!/usr/bin/env python3
"""
Docker Compose Version Checker

This script scans a directory and its subdirectories for docker-compose.yml files,
extracts image tags, and compares them with the latest available versions on Docker Hub.
It will notify you if newer versions are available for any of your Docker images.
"""

import os
import sys
import yaml
import argparse
import re
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple, Optional


class DockerVersionChecker:
    def __init__(self, directory: str, verbose: bool = False):
        """
        Initialize the Docker version checker.
        
        Args:
            directory: The directory to scan for docker-compose.yml files
            verbose: Whether to print verbose output
        """
        self.directory = directory
        self.verbose = verbose
        # Store results to avoid redundant API calls for the same image
        self.checked_images = {}

    def find_docker_compose_files(self) -> List[Path]:
        """
        Find all docker-compose.yml files in the specified directory and its subdirectories.
        
        Returns:
            A list of paths to docker-compose.yml files
        """
        if self.verbose:
            print(f"Scanning directory: {self.directory}")
        
        compose_files = []
        
        for root, _, files in os.walk(self.directory):
            for file in files:
                if file in ['docker-compose.yml', 'docker-compose.yaml']:
                    compose_files.append(Path(root) / file)
        
        if self.verbose:
            print(f"Found {len(compose_files)} Docker Compose files")
        
        return compose_files

    def extract_images_from_compose(self, compose_file: Path) -> List[str]:
        """
        Extract image references from a docker-compose.yml file.
        
        Args:
            compose_file: Path to the docker-compose.yml file
            
        Returns:
            A list of image references with tags
        """
        try:
            with open(compose_file, 'r') as file:
                compose_data = yaml.safe_load(file)
                
            if not compose_data or 'services' not in compose_data:
                if self.verbose:
                    print(f"No services found in {compose_file}")
                return []
            
            images = []
            for service_name, service_config in compose_data['services'].items():
                if 'image' in service_config:
                    image = service_config['image']
                    images.append(image)
                    if self.verbose:
                        print(f"Found image in {compose_file}: {image}")
            
            return images
        
        except Exception as e:
            print(f"Error parsing {compose_file}: {e}")
            return []

    def parse_image_reference(self, image_ref: str) -> Tuple[str, str]:
        """
        Parse an image reference into repository and tag.
        
        Args:
            image_ref: The image reference, e.g., 'nginx:1.21.0'
            
        Returns:
            A tuple of (repository, tag)
        """
        if ':' in image_ref:
            repo, tag = image_ref.rsplit(':', 1)
        else:
            repo, tag = image_ref, 'latest'
        
        # Handle Docker Hub official images
        if '/' not in repo:
            repo = f"library/{repo}"
        
        # Handle repository with registry
        if repo.count('/') > 1:
            # This is a repository with registry (e.g., registry.example.com/my-org/my-image)
            # Extract just the repository part for Docker Hub comparison
            registry_domain = repo.split('/', 1)[0]
            if '.' in registry_domain or ':' in registry_domain:
                # This is not a Docker Hub image, so we can't check it
                return None, None
        
        return repo, tag

    def get_latest_tag(self, repository: str) -> Optional[str]:
        """
        Get the latest version tag for a Docker image repository.
        
        Args:
            repository: The Docker repository, e.g., 'library/nginx'
            
        Returns:
            The latest semantic version tag, or None if not found
        """
        # Skip if private repository
        if repository is None:
            return None
            
        # Use Docker Hub API to get tags
        if repository in self.checked_images:
            return self.checked_images[repository]
            
        try:
            # Docker Hub API for tags
            url = f"https://hub.docker.com/v2/repositories/{repository}/tags"
            response = requests.get(url)
            
            if response.status_code != 200:
                if self.verbose:
                    print(f"Failed to get tags for {repository}: HTTP {response.status_code}")
                return None
                
            data = response.json()
            
            # Filter out non-version tags and sort them
            version_tags = []
            for tag_info in data.get('results', []):
                tag_name = tag_info['name']
                # Try to match semantic version patterns
                if re.match(r'^v?\d+(\.\d+)*$', tag_name):
                    version_tags.append(tag_name)
            
            if not version_tags:
                if self.verbose:
                    print(f"No version tags found for {repository}")
                return None
                
            # Sort by version components
            latest_tag = self._sort_version_tags(version_tags)
            self.checked_images[repository] = latest_tag
            
            return latest_tag
            
        except Exception as e:
            print(f"Error getting tags for {repository}: {e}")
            return None

    def _sort_version_tags(self, tags: List[str]) -> str:
        """
        Sort version tags and return the latest one.
        
        Args:
            tags: List of version tags
            
        Returns:
            The latest version tag
        """
        def version_key(tag):
            # Remove 'v' prefix if present
            if tag.startswith('v'):
                tag = tag[1:]
            
            # Split the version into components
            components = []
            for part in tag.split('.'):
                try:
                    components.append(int(part))
                except ValueError:
                    components.append(part)
            
            return components
        
        # Sort tags by version components
        sorted_tags = sorted(tags, key=version_key)
        
        # Return the highest version
        return sorted_tags[-1] if sorted_tags else None

    def compare_versions(self, current_tag: str, latest_tag: str) -> bool:
        """
        Compare current version with the latest version.
        
        Args:
            current_tag: The current version tag
            latest_tag: The latest version tag
            
        Returns:
            True if an update is available, False otherwise
        """
        if current_tag == latest_tag:
            return False
            
        # Remove 'v' prefix if present
        current = current_tag[1:] if current_tag.startswith('v') else current_tag
        latest = latest_tag[1:] if latest_tag.startswith('v') else latest_tag
        
        # Split versions into components
        current_parts = current.split('.')
        latest_parts = latest.split('.')
        
        # Compare each component
        for i in range(min(len(current_parts), len(latest_parts))):
            try:
                current_part = int(current_parts[i])
                latest_part = int(latest_parts[i])
                
                if latest_part > current_part:
                    return True
                elif current_part > latest_part:
                    return False
            except ValueError:
                # If we can't compare as integers, use string comparison
                if latest_parts[i] > current_parts[i]:
                    return True
                elif current_parts[i] > latest_parts[i]:
                    return False
        
        # If we've compared all components and they're equal, check if latest has more components
        return len(latest_parts) > len(current_parts)

    def check_images(self) -> Dict[str, Dict]:
        """
        Check all Docker images in all compose files.
        
        Returns:
            A dictionary of update information
        """
        compose_files = self.find_docker_compose_files()
        all_updates = {}
        
        for compose_file in compose_files:
            updates = self.check_images_in_file(compose_file)
            if updates:
                all_updates[str(compose_file)] = updates
                
        return all_updates

    def check_images_in_file(self, compose_file: Path) -> Dict:
        """
        Check all Docker images in a specific compose file.
        
        Args:
            compose_file: Path to the docker-compose.yml file
            
        Returns:
            A dictionary of update information for this file
        """
        images = self.extract_images_from_compose(compose_file)
        updates = {}
        
        for image_ref in images:
            repo, current_tag = self.parse_image_reference(image_ref)
            
            # Skip if we couldn't parse the image reference
            if repo is None:
                if self.verbose:
                    print(f"Skipping non-Docker Hub image: {image_ref}")
                continue
                
            latest_tag = self.get_latest_tag(repo)
            
            # Skip if we couldn't get the latest tag
            if latest_tag is None:
                if self.verbose:
                    print(f"Couldn't determine latest tag for {repo}")
                continue
                
            update_available = self.compare_versions(current_tag, latest_tag)
            
            if update_available:
                # Convert library/repo to just repo for display
                display_repo = repo.replace('library/', '', 1)
                updates[image_ref] = {
                    'current': current_tag,
                    'latest': latest_tag,
                    'repository': display_repo
                }
                
        return updates

    def run(self) -> None:
        """
        Run the Docker version checker and display results.
        """
        print("Docker Compose Version Checker")
        print("------------------------------")
        print(f"Scanning directory: {self.directory}")
        print()
        
        updates = self.check_images()
        
        if not updates:
            print("✅ All Docker images are up-to-date!")
            return
            
        print("🔄 Update(s) available:")
        print()
        
        for compose_file, file_updates in updates.items():
            print(f"📄 {compose_file}:")
            
            for image_ref, update_info in file_updates.items():
                current = update_info['current']
                latest = update_info['latest']
                repo = update_info['repository']
                
                print(f"  • {repo}:{current} → {latest}")
            
            print()


def main():
    parser = argparse.ArgumentParser(description='Check Docker Compose files for outdated image versions')
    parser.add_argument('-d', '--directory', default='.', 
                        help='Directory to scan for docker-compose.yml files (default: current directory)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose output')
    
    args = parser.parse_args()
    
    checker = DockerVersionChecker(args.directory, args.verbose)
    checker.run()


if __name__ == "__main__":
    main()
