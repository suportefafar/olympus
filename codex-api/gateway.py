#!/usr/bin/env python3
"""Small authenticated HTTP adapter for the locally signed-in Codex CLI."""

import hmac
import json
import os
import re
import subprocess
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


HOST = "127.0.0.1"
PORT = 18094
MAX_BODY = 256 * 1024
MAX_MESSAGES = 80
MAX_CHARS = 180_000
TIMEOUT = 570
EFFORTS = {"low", "medium", "high", "xhigh", "max"}
MODEL_PATTERN = re.compile(r"\A[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}\Z")
TOKEN = os.environ["CODEX_API_TOKEN"]
CODEX_BIN = os.environ.get("CODEX_BIN", "/opt/codex-api/bin/codex")
WORKDIR = Path(os.environ.get("CODEX_WORKDIR", "/var/lib/codex-api/work"))
MODELS = tuple(part.strip() for part in os.environ.get("CODEX_ALLOWED_MODELS", "gpt-6.1-sol,gpt-6-astra,gpt-6-luna").split(",") if part.strip())
DEFAULT_MODEL = os.environ.get("CODEX_DEFAULT_MODEL", MODELS[0])
SLOTS = threading.BoundedSemaphore(2)


def validate_request(body):
    if not isinstance(body, dict):
        raise ValueError("O corpo deve ser um objeto JSON.")
    model = body.get("model", DEFAULT_MODEL)
    effort = body.get("reasoning_effort", "medium")
    if not isinstance(model, str) or not MODEL_PATTERN.fullmatch(model) or model not in MODELS:
        raise ValueError("Modelo não permitido.")
    if not isinstance(effort, str) or effort not in EFFORTS:
        raise ValueError("Nível de esforço inválido.")
    if body.get("stream", False) is not False:
        raise ValueError("Streaming ainda não é suportado.")
    messages = body.get("messages")
    if not isinstance(messages, list) or not 1 <= len(messages) <= MAX_MESSAGES:
        raise ValueError("Envie de 1 a 80 mensagens.")
    lines = []
    for item in messages:
        if not isinstance(item, dict) or item.get("role") not in ("system", "developer", "user", "assistant") or not isinstance(item.get("content"), str):
            raise ValueError("As mensagens devem conter role e content textual.")
        lines.append(f"{item['role'].upper()}:\n{item['content']}")
    prompt = "Você é um assistente de texto. Responda à última mensagem do usuário usando o contexto abaixo. Não execute comandos nem acesse arquivos locais.\n\n" + "\n\n".join(lines)
    if len(prompt) > MAX_CHARS:
        raise ValueError("A conversa excede o limite de tamanho.")
    return model, effort, prompt


def generate(model, effort, prompt):
    WORKDIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="request-", dir=WORKDIR) as directory:
        answer_path = Path(directory) / "answer.txt"
        command = [
            CODEX_BIN, "--ask-for-approval", "never", "exec", "--ignore-user-config",
            "--ephemeral", "--skip-git-repo-check", "--sandbox", "read-only",
            "--model", model, "--config", f'model_reasoning_effort="{effort}"',
            "--cd", directory, "--output-last-message", str(answer_path), "-",
        ]
        # Do not pass the gateway credential into the agent's process.
        environment = {key: value for key, value in os.environ.items() if key not in ("CODEX_API_TOKEN",)}
        result = subprocess.run(command, input=prompt, text=True, capture_output=True, timeout=TIMEOUT, env=environment, check=False)
        if result.returncode:
            raise RuntimeError(f"Codex terminou com código {result.returncode}.")
        answer = answer_path.read_text(encoding="utf-8").strip() if answer_path.exists() else ""
        if not answer:
            raise RuntimeError("Codex não retornou uma resposta.")
        return answer


class Handler(BaseHTTPRequestHandler):
    server_version = "CodexAPI/1"

    def log_message(self, format_string, *args):
        # Never log Authorization headers or request bodies.
        print("%s %s" % (self.address_string(), format_string % args), flush=True)

    def reply(self, status, data):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def authenticated(self):
        header = self.headers.get("Authorization", "")
        candidate = header[7:] if header.startswith("Bearer ") else ""
        if not candidate or not hmac.compare_digest(candidate, TOKEN):
            self.reply(401, {"error": {"message": "Bearer token inválido.", "type": "authentication_error"}})
            return False
        return True

    def do_GET(self):
        if self.path == "/healthz":
            return self.reply(200, {"status": "ok"})
        if not self.authenticated():
            return
        if self.path == "/v1/models":
            return self.reply(200, {"object": "list", "data": [{"id": model, "object": "model"} for model in MODELS]})
        self.reply(404, {"error": {"message": "Rota inexistente."}})

    def do_POST(self):
        if not self.authenticated():
            return
        if self.path != "/v1/chat/completions":
            return self.reply(404, {"error": {"message": "Rota inexistente."}})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                return self.reply(413, {"error": {"message": "Corpo ausente ou muito grande."}})
            model, effort, prompt = validate_request(json.loads(self.rfile.read(length)))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            return self.reply(400, {"error": {"message": str(error), "type": "invalid_request_error"}})
        if not SLOTS.acquire(blocking=False):
            return self.reply(429, {"error": {"message": "Serviço ocupado; tente novamente."}})
        try:
            answer = generate(model, effort, prompt)
        except subprocess.TimeoutExpired:
            return self.reply(504, {"error": {"message": "Codex excedeu o tempo limite."}})
        except Exception as error:
            print(f"generation failed: {type(error).__name__}: {error}", flush=True)
            return self.reply(502, {"error": {"message": str(error), "type": "upstream_error"}})
        finally:
            SLOTS.release()
        self.reply(200, {
            "id": "chatcmpl-" + uuid.uuid4().hex,
            "object": "chat.completion", "created": int(time.time()), "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
        })


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
