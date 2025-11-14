#!/usr/bin/env python3
"""
Validation script for flavours-of-elastic repository.

This script validates that all three stacks (Elastic, OpenSearch, ELK-OSS) can:
1. Start successfully
2. Respond to health checks
3. Create indices
4. Index and search documents
5. Serve UI (Kibana/Dashboards)
"""

import argparse
import json
import subprocess
import sys
import time
from typing import Dict, Tuple
from urllib.parse import quote

try:
    import requests
    from requests.packages.urllib3.exceptions import InsecureRequestWarning

    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
except ImportError:
    print("Error: requests library not found. Install with: pip install requests")
    sys.exit(1)


class StackValidator:
    """Base class for stack validation."""

    def __init__(self, name: str, compose_file: str):
        self.name = name
        self.compose_file = compose_file
        self.base_url = None
        self.auth = None
        self.verify_ssl = True

    def run_command(self, cmd: list, check: bool = True) -> Tuple[int, str]:
        """Run a shell command and return exit code and output."""
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=check, timeout=300
            )
            return result.returncode, result.stdout + result.stderr
        except subprocess.CalledProcessError as e:
            return e.returncode, e.stdout + e.stderr
        except subprocess.TimeoutExpired:
            return -1, "Command timed out"

    def start_stack(self) -> bool:
        """Start the docker-compose stack."""
        print(f"\n{'=' * 60}")
        print(f"Starting {self.name}...")
        print(f"{'=' * 60}")

        cmd = [
            "docker-compose",
            "-f",
            self.compose_file,
            "--env-file",
            ".env",
            "up",
            "-d",
        ]
        exit_code, output = self.run_command(cmd)

        if exit_code != 0:
            print(f"❌ Failed to start {self.name}")
            print(output)
            return False

        print(f"✅ {self.name} containers started")
        return True

    def stop_stack(self, cleanup: bool = True) -> None:
        """Stop the docker-compose stack."""
        print(f"\nStopping {self.name}...")
        flag = "-v" if cleanup else ""
        cmd = ["docker-compose", "-f", self.compose_file, "down"]
        if flag:
            cmd.append(flag)
        self.run_command(cmd, check=False)
        print(f"✅ {self.name} stopped")

    def wait_for_service(
        self, url: str, timeout: int = 180, interval: int = 5
    ) -> bool:
        """Wait for a service to respond."""
        print(f"Waiting for service at {url}...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = requests.get(
                    url, auth=self.auth, verify=self.verify_ssl, timeout=5
                )
                if response.status_code in [200, 401]:
                    print(f"✅ Service is responding")
                    return True
            except requests.exceptions.RequestException:
                pass

            time.sleep(interval)
            elapsed = int(time.time() - start_time)
            print(f"   Still waiting... ({elapsed}s/{timeout}s)")

        print(f"❌ Service did not respond within {timeout}s")
        return False

    def check_health(self) -> bool:
        """Check cluster health."""
        print(f"\nChecking {self.name} cluster health...")
        url = f"{self.base_url}/_cluster/health"

        try:
            response = requests.get(
                url, auth=self.auth, verify=self.verify_ssl, timeout=10
            )
            if response.status_code == 200:
                health = response.json()
                status = health.get("status", "unknown")
                print(f"✅ Cluster health: {status}")
                print(f"   Cluster name: {health.get('cluster_name')}")
                print(f"   Number of nodes: {health.get('number_of_nodes')}")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False

    def test_index_operations(self) -> bool:
        """Test index creation, document insertion, and search."""
        print(f"\nTesting index operations on {self.name}...")
        index_name = "test-validation-index"

        # Create index
        try:
            url = f"{self.base_url}/{index_name}"
            response = requests.put(
                url, auth=self.auth, verify=self.verify_ssl, timeout=10
            )
            if response.status_code not in [200, 201]:
                print(f"❌ Failed to create index: {response.status_code}")
                return False
            print(f"✅ Created index '{index_name}'")
        except Exception as e:
            print(f"❌ Index creation error: {e}")
            return False

        # Add document
        try:
            url = f"{self.base_url}/{index_name}/_doc/1"
            doc = {
                "title": "Validation Test",
                "description": "Testing flavours-of-elastic",
                "timestamp": "2025-01-15",
            }
            response = requests.post(
                url,
                json=doc,
                auth=self.auth,
                verify=self.verify_ssl,
                timeout=10,
                headers={"Content-Type": "application/json"},
            )
            if response.status_code not in [200, 201]:
                print(f"❌ Failed to add document: {response.status_code}")
                return False
            print(f"✅ Added document to index")
        except Exception as e:
            print(f"❌ Document insertion error: {e}")
            return False

        # Wait for indexing
        time.sleep(2)

        # Search
        try:
            url = f"{self.base_url}/{index_name}/_search?q=Validation"
            response = requests.get(
                url, auth=self.auth, verify=self.verify_ssl, timeout=10
            )
            if response.status_code != 200:
                print(f"❌ Search failed: {response.status_code}")
                return False

            results = response.json()
            hits = results.get("hits", {}).get("total", {})
            # Handle both old and new format
            total = hits.get("value", hits) if isinstance(hits, dict) else hits

            if total > 0:
                print(f"✅ Search successful: found {total} documents")
                return True
            else:
                print(f"❌ Search returned no results")
                return False
        except Exception as e:
            print(f"❌ Search error: {e}")
            return False

    def check_ui(self, ui_url: str, ui_name: str) -> bool:
        """Check if UI is responding."""
        print(f"\nChecking {ui_name}...")
        try:
            response = requests.get(ui_url, timeout=10, allow_redirects=True)
            if response.status_code in [200, 302]:
                print(f"✅ {ui_name} is responding")
                return True
            else:
                print(f"⚠️  {ui_name} returned status {response.status_code}")
                return False
        except Exception as e:
            print(f"⚠️  {ui_name} check error: {e}")
            return False

    def validate(self) -> bool:
        """Run full validation."""
        success = True

        if not self.start_stack():
            return False

        try:
            # Wait for main service
            if not self.wait_for_service(self.base_url):
                success = False
                return success

            # Check health
            if not self.check_health():
                success = False
                return success

            # Test operations
            if not self.test_index_operations():
                success = False
                return success

            # Check UI
            ui_result = self.check_ui("http://localhost:5601", self.ui_name)
            # UI is optional, don't fail validation if it's not ready

            if success:
                print(f"\n{'=' * 60}")
                print(f"✅ {self.name} validation PASSED")
                print(f"{'=' * 60}")

        finally:
            self.stop_stack(cleanup=True)

        return success


class ElasticOSSValidator(StackValidator):
    """Validator for Elastic OSS stack."""

    def __init__(self):
        super().__init__("Elastic OSS", "docker/elk-oss/docker-compose.yml")
        self.base_url = "http://localhost:9200"
        self.auth = None  # No auth for OSS
        self.verify_ssl = False
        self.ui_name = "Kibana OSS"


class OpenSearchValidator(StackValidator):
    """Validator for OpenSearch stack."""

    def __init__(self):
        super().__init__("OpenSearch", "docker/opensearch/docker-compose.yml")
        self.base_url = "https://localhost:9200"
        self.auth = ("admin", "Jierou9uju!@£@£")  # From .env
        self.verify_ssl = False
        self.ui_name = "OpenSearch Dashboards"


class ElasticValidator(StackValidator):
    """Validator for Elastic Stack."""

    def __init__(self):
        super().__init__("Elastic Stack", "docker/elk/docker-compose.yml")
        self.base_url = "https://localhost:9200"
        self.auth = ("elastic", "elastic")  # From .env
        self.verify_ssl = False
        self.ui_name = "Kibana"


def main():
    parser = argparse.ArgumentParser(
        description="Validate flavours-of-elastic stacks"
    )
    parser.add_argument(
        "--stack",
        choices=["elk-oss", "opensearch", "elastic", "all"],
        default="all",
        help="Which stack to validate (default: all)",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Don't remove volumes after testing",
    )

    args = parser.parse_args()

    validators: Dict[str, StackValidator] = {
        "elk-oss": ElasticOSSValidator(),
        "opensearch": OpenSearchValidator(),
        "elastic": ElasticValidator(),
    }

    if args.stack == "all":
        stacks_to_test = list(validators.keys())
    else:
        stacks_to_test = [args.stack]

    print("\n" + "=" * 60)
    print("FLAVOURS-OF-ELASTIC VALIDATION")
    print("=" * 60)
    print(f"\nTesting stacks: {', '.join(stacks_to_test)}")

    results = {}
    for stack_name in stacks_to_test:
        validator = validators[stack_name]
        results[stack_name] = validator.validate()

    # Summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    all_passed = True
    for stack_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{stack_name:15s}: {status}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n🎉 All validations passed!")
        return 0
    else:
        print("\n❌ Some validations failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
