import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import stacks
from scripts.stacks import (
    REPO_ROOT,
    STACKS,
    StackError,
    connection,
    get_stack,
    load_env,
)
from validate import build_parser, plan_checks

ENV_EXAMPLE = REPO_ROOT / ".env.example"


def write_env(text):
    handle = tempfile.NamedTemporaryFile("w", suffix=".env", delete=False)
    handle.write(text)
    handle.close()
    return Path(handle.name)


class LoadEnvTests(unittest.TestCase):
    def test_parses_comments_quotes_and_export(self):
        path = write_env(
            "# comment\n\nexport A=1\nB='two words'\nC=\"quoted\"\nD=value # trailing\nE=pass#word\n"
        )
        with mock.patch.dict(os.environ, {}, clear=False):
            for key in "ABCDE":
                os.environ.pop(key, None)
            env = load_env(path)
        self.assertEqual(
            env,
            {"A": "1", "B": "two words", "C": "quoted", "D": "value", "E": "pass#word"},
        )

    def test_process_environment_wins_like_compose(self):
        path = write_env("ELK_VERSION=1.2.3\n")
        with mock.patch.dict(os.environ, {"ELK_VERSION": "9.9.9"}):
            self.assertEqual(load_env(path)["ELK_VERSION"], "9.9.9")


class RegistryTests(unittest.TestCase):
    def test_registry_matches_docker_directories(self):
        on_disk = {p.parent.name for p in REPO_ROOT.glob("docker/*/docker-compose.yml")}
        self.assertEqual(on_disk, set(STACKS))

    def test_env_example_defines_every_version_and_licence_variable(self):
        env = load_env(ENV_EXAMPLE)
        for stack in STACKS.values():
            self.assertTrue(env.get(stack.version_var), stack.version_var)
            if stack.licence_var:
                self.assertIn(
                    env[stack.licence_var], ("basic", "trial"), stack.licence_var
                )
            if stack.password_var:
                self.assertTrue(env.get(stack.password_var), stack.password_var)

    def test_aliases_and_unknown_names(self):
        self.assertEqual(get_stack("elastic").name, "elk")
        with self.assertRaises(StackError):
            get_stack("nope")

    def test_capabilities_follow_the_licence(self):
        elk_single = get_stack("elk-single")
        self.assertNotIn("rrf", elk_single.capabilities({"LICENSE": "basic"}))
        self.assertIn("rrf", elk_single.capabilities({"LICENSE": "trial"}))
        self.assertIn("ml", get_stack("elk-ml").capabilities({}))  # trial by default
        self.assertEqual(
            get_stack("opensearch").capabilities({}), frozenset({"os_knn"})
        )
        self.assertEqual(get_stack("elk-oss").capabilities({}), frozenset())

    def test_course_tracks(self):
        days = {
            name: stack.course_days
            for name, stack in STACKS.items()
            if stack.course_days
        }
        self.assertEqual(days["elk-single"], (1, 2, 3))
        self.assertEqual(days["elk-9"], (1, 2, 3))
        self.assertEqual(days["elk-ml"], (4,))
        self.assertEqual(days["elk-ml-9"], (4,))  # dual track: 8.19 + 9.x

    def test_describe_never_contains_password_values(self):
        env = {
            **load_env(ENV_EXAMPLE),
            "ELASTIC_PASSWORD": "Sentinel-1!",
            "OPENSEARCH_INITIAL_ADMIN_PASSWORD": "S-2!",
        }
        blob = json.dumps([stack.describe(env) for stack in STACKS.values()])
        self.assertNotIn("Sentinel-1!", blob)
        self.assertNotIn("S-2!", blob)

    def test_port_offset_and_exported_environment(self):
        env = {
            "ELK_VERSION": "8.19.22",
            "ELASTIC_PASSWORD": "pw",
            "ELK_ML_LICENSE": "trial",
        }
        conn = connection(get_stack("elk-ml"), env, port_offset=10000)
        self.assertEqual(conn.url, "https://localhost:19200")
        self.assertEqual(conn.ui_url, "http://localhost:15601")
        exported = conn.export_env()
        self.assertEqual(exported["ELASTIC_PASSWORD"], "pw")
        self.assertEqual(exported["FOE_TRACK"], "8.19")
        self.assertIn("rrf", exported["FOE_CAPABILITIES"].split(","))
        self.assertEqual(
            connection(get_stack("elk-oss"), {}).export_env()["ELASTIC_NO_AUTH"], "true"
        )

    def test_oneshot_fallback_parsing(self):
        stack = get_stack("elk-single")
        ok = "\n".join(
            json.dumps(row)
            for row in (
                {"Service": "setup", "State": "exited", "ExitCode": 0, "Health": ""},
                {
                    "Service": "elasticsearch",
                    "State": "running",
                    "ExitCode": 0,
                    "Health": "healthy",
                },
            )
        )
        self.assertTrue(stacks._only_oneshots_exited_cleanly(stack, ok))
        failed_setup = ok.replace(
            '"ExitCode": 0, "Health": ""', '"ExitCode": 1, "Health": ""', 1
        )
        self.assertFalse(stacks._only_oneshots_exited_cleanly(stack, failed_setup))
        self.assertFalse(stacks._only_oneshots_exited_cleanly(stack, ""))


class ValidatePlanTests(unittest.TestCase):
    def plan(self, name, env):
        return [check for check, _ in plan_checks(connection(get_stack(name), env))]

    def test_check_selection_per_stack(self):
        self.assertEqual(
            self.plan("elk-single", {"LICENSE": "basic"}),
            ["identity", "cluster", "license", "crud", "vectors", "ui"],
        )
        self.assertEqual(
            self.plan("elk-ml", {}),
            ["identity", "cluster", "license", "crud", "vectors", "ml", "rrf", "ui"],
        )
        self.assertEqual(
            self.plan("opensearch-3", {}),
            ["identity", "cluster", "crud", "vectors", "ui"],
        )
        self.assertEqual(
            self.plan("elk-oss", {}), ["identity", "cluster", "crud", "ui"]
        )

    def test_cli_defaults(self):
        args = build_parser().parse_args([])
        self.assertEqual(args.stack, "all")
        self.assertFalse(args.keep)


if __name__ == "__main__":
    unittest.main()
