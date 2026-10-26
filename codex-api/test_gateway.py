import http.client
import importlib.util
import json
import os
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault("CODEX_API_TOKEN", "test-token")
spec = importlib.util.spec_from_file_location("codex_gateway", Path(__file__).with_name("gateway.py"))
gateway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway)


class GatewayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), gateway.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def request(self, method, path, body=None, token=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1])
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        encoded = json.dumps(body).encode() if body is not None else None
        if encoded is not None:
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=encoded, headers=headers)
        response = conn.getresponse()
        result = response.status, json.loads(response.read())
        conn.close()
        return result

    def test_authentication_and_model_catalog(self):
        self.assertEqual(401, self.request("GET", "/v1/models")[0])
        status, data = self.request("GET", "/v1/models", token="test-token")
        self.assertEqual(200, status)
        self.assertIn("gpt-6.1-sol", [model["id"] for model in data["data"]])

    def test_request_validates_model_and_effort_before_running_codex(self):
        with patch.object(gateway, "generate", return_value="Olá") as generate:
            body = {"model": "gpt-6.1-sol", "reasoning_effort": "high", "messages": [{"role": "user", "content": "Oi"}]}
            status, data = self.request("POST", "/v1/chat/completions", body, "test-token")
            self.assertEqual(200, status)
            self.assertEqual("Olá", data["choices"][0]["message"]["content"])
            generate.assert_called_once_with("gpt-6.1-sol", "high", unittest.mock.ANY)
            body["reasoning_effort"] = ["high"]
            self.assertEqual(400, self.request("POST", "/v1/chat/completions", body, "test-token")[0])
            body["reasoning_effort"] = "high"
            body["model"] = "../../etc/passwd"
            self.assertEqual(400, self.request("POST", "/v1/chat/completions", body, "test-token")[0])
            self.assertEqual(1, generate.call_count)


if __name__ == "__main__":
    unittest.main()
