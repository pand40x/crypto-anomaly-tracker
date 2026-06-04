import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DeploymentConfigTests(unittest.TestCase):
    def test_compose_is_exposed_through_dokploy_domain_not_host_port(self):
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

        self.assertNotIn("PUBLISHED_PORT", compose)
        self.assertNotIn("18080", compose)
        self.assertNotIn("ports:", compose)
        self.assertIn("ANOMALY_PUBLIC_BASE_URL: ${ANOMALY_PUBLIC_BASE_URL:-https://anomaly.anilsahin.tr}", compose)

    def test_deploy_helpers_write_anomaly_domain_without_public_port(self):
        deploy_script = (ROOT / "scripts" / "dokploy_deploy.py").read_text(encoding="utf-8")
        local_env_script = (ROOT / "scripts" / "write_local_env_from_keychain.sh").read_text(encoding="utf-8")

        for text in (deploy_script, local_env_script):
            self.assertNotIn("PUBLISHED_PORT=", text)
            self.assertNotIn("18080", text)
            self.assertIn("ANOMALY_PUBLIC_BASE_URL", text)
            self.assertIn("https://anomaly.anilsahin.tr", text)


if __name__ == "__main__":
    unittest.main()
