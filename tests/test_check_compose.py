import unittest

from scripts.check_compose import SENTINELS, check_raw, check_rendered

DEFAULT_PORTS = {9200: "9200", 5601: "5601"}
SECRETS = list(SENTINELS.values())


def compliant_config():
    return {
        "services": {
            "setup": {"image": "es:8.19.22"},
            "es": {
                "image": "es:8.19.22",
                "mem_limit": "2147483648",
                "healthcheck": {"test": ["CMD-SHELL", 'curl -u "elastic:${ELASTIC_PASSWORD}" localhost']},
                "ports": [{"target": 9200, "published": "9200", "host_ip": "127.0.0.1"}],
            },
            "kibana": {
                "image": "kibana:8.19.22",
                "mem_limit": "2147483648",
                "healthcheck": {"test": ["CMD-SHELL", "curl -fs localhost:5601/api/status"]},
                "ports": [{"target": 5601, "published": "5601", "host_ip": "127.0.0.1"}],
                "depends_on": {"setup": {"condition": "service_completed_successfully"}},
            },
        }
    }


class CheckComposeTests(unittest.TestCase):
    def check(self, config):
        return check_rendered(config, SECRETS, "127.0.0.1", DEFAULT_PORTS)

    def test_compliant_config_passes(self):
        self.assertEqual(self.check(compliant_config()), [])

    def test_raw_flags_version_key_and_container_name(self):
        problems = check_raw('version: "3.8"\nservices:\n  es:\n    container_name: es\n')
        self.assertEqual(len(problems), 2)

    def test_port_on_all_interfaces_is_flagged(self):
        config = compliant_config()
        config["services"]["es"]["ports"][0].pop("host_ip")
        self.assertIn("bound to 0.0.0.0", " ".join(self.check(config)))

    def test_unexpected_port_is_flagged(self):
        config = compliant_config()
        config["services"]["es"]["ports"].append({"target": 9600, "published": "9600", "host_ip": "127.0.0.1"})
        self.assertIn("unexpected published port 9600", " ".join(self.check(config)))

    def test_port_override_must_take_effect(self):
        problems = check_rendered(compliant_config(), SECRETS, "127.0.0.1", {9200: "19200", 5601: "15601"})
        self.assertEqual(len(problems), 2)

    def test_missing_mem_limit_and_healthcheck(self):
        config = compliant_config()
        del config["services"]["es"]["mem_limit"]
        del config["services"]["es"]["healthcheck"]
        joined = " ".join(self.check(config))
        self.assertIn("missing mem_limit", joined)
        self.assertIn("missing healthcheck", joined)

    def test_oneshot_without_dependent_is_flagged(self):
        config = compliant_config()
        config["services"]["kibana"]["depends_on"] = {"setup": {"condition": "service_healthy"}}
        self.assertIn("one-shot service has no dependent", " ".join(self.check(config)))

    def test_password_in_healthcheck_is_flagged(self):
        config = compliant_config()
        secret = SENTINELS["ELASTIC_PASSWORD"]
        config["services"]["es"]["healthcheck"]["test"] = ["CMD", "curl", "-u", f"elastic:{secret}", "localhost"]
        self.assertIn("password value appears", " ".join(self.check(config)))

    def test_untagged_or_latest_image_is_flagged(self):
        config = compliant_config()
        config["services"]["es"]["image"] = "docker.elastic.co/elasticsearch/elasticsearch"
        config["services"]["kibana"]["image"] = "kibana:latest"
        self.assertEqual(sum("explicit version tag" in p for p in self.check(config)), 2)


if __name__ == "__main__":
    unittest.main()
