#!/usr/bin/env python3
"""Apply only production logging changes, preserving running image revisions."""
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def output(command):
    return subprocess.check_output(command, text=True)


def inspect(ids):
    return json.loads(output(["docker", "inspect", *ids]))


def info(message):
    print(f"[INFO] {message}", flush=True)


def baseline_command(compose):
    baseline = []
    index = 0
    found = False
    while index < len(compose):
        if (compose[index] == "-f" and index + 1 < len(compose)
                and Path(compose[index + 1]).name == "compose.logging.yaml"):
            found = True
            index += 2
        else:
            baseline.append(compose[index])
            index += 1
    if not found:
        raise RuntimeError("Production logging overlay is missing.")
    return baseline


def image_id(reference):
    try:
        result = subprocess.check_output(["docker", "image", "inspect", reference],
                                         text=True, stderr=subprocess.DEVNULL)
        return json.loads(result)[0]["Id"]
    except subprocess.CalledProcessError:
        return None


def ready(compose, service, image, logging, was_healthy, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        ids = output([*compose, "ps", "--all", "--quiet", service]).split()
        if len(ids) != 1:
            raise RuntimeError(f"{service}: expected exactly one container after recreation.")
        container = inspect(ids)[0]
        if container["Image"] != image:
            raise RuntimeError(f"{service}: running image changed unexpectedly.")
        if container["HostConfig"]["LogConfig"] != logging:
            raise RuntimeError(f"{service}: effective log policy does not match the requested limit.")
        state = container["State"]
        if state["Status"] == "running":
            if not was_healthy or state.get("Health", {}).get("Status") == "healthy":
                return
        if state["Status"] in ("exited", "dead"):
            raise RuntimeError(f"{service}: container failed to start; inspect its logs.")
        time.sleep(2)
    raise RuntimeError(f"{service}: did not recover its previous readiness within {timeout}s.")


def apply(compose, allow_current_images=False):
    model = json.loads(output([*compose, "config", "--format", "json"]))
    hashes = dict(line.split() for line in output(
        [*baseline_command(compose), "config", "--hash", "*"]).splitlines() if line.strip())
    ids = output([*compose, "ps", "--all", "--quiet"]).split()
    containers = inspect(ids) if ids else []
    pending = {}
    unavailable = []
    for container in containers:
        if container["State"]["Status"] != "running":
            continue
        labels = container["Config"]["Labels"]
        service = labels.get("com.docker.compose.service")
        if service not in model["services"]:
            raise RuntimeError(f"{service}: running service is absent from Compose configuration.")
        policy = model["services"][service].get("logging")
        if not policy or policy.get("driver") != "json-file":
            raise RuntimeError(f"{service}: missing json-file rotation policy.")
        desired = {"Type": policy["driver"], "Config": policy["options"]}
        if container["HostConfig"]["LogConfig"] == desired:
            continue
        if labels.get("com.docker.compose.config-hash") != hashes.get(service):
            raise RuntimeError(f"{service}: unrelated Compose configuration drift; refusing to deploy.")
        if service in pending:
            raise RuntimeError(f"{service}: multiple replicas require a separate rollout.")
        target_image = image_id(container["Image"])
        if target_image is None:
            if allow_current_images:
                target_image = image_id(container["Config"]["Image"])
                if target_image is None:
                    raise RuntimeError(f"{service}: neither running nor configured image is available locally.")
                info(f"{service}: using the approved locally available image {target_image}.")
            else:
                unavailable.append(service)
                info(f"Deferring {service}: its running image is unavailable locally.")
                continue
        pending[service] = (container, desired, target_image)
    if not pending:
        if unavailable:
            raise RuntimeError("Running images unavailable; deferred: " + ", ".join(sorted(unavailable)))
        info("All running services already have the requested log rotation policy.")
        return

    # All drift checks finish before changing any containers. Pin images because a
    # mutable tag may have been rebuilt since a running container was created.
    overrides = {"services": {service: {"image": item[2], "pull_policy": "never"}
                             for service, item in pending.items()}}
    with tempfile.TemporaryDirectory(prefix="olympus-logging-") as directory:
        override = Path(directory) / "images.json"
        override.write_text(json.dumps(overrides))
        override.chmod(0o600)
        command = [*compose, "-f", str(override)]
        subprocess.run([*command, "config", "--quiet"], check=True)
        remaining = set(pending)
        order = []
        while remaining:
            available = sorted(service for service in remaining if not (
                set(model["services"][service].get("depends_on", {})) & remaining))
            if not available:
                raise RuntimeError("Circular service dependencies prevent a sequential rollout.")
            order.extend(available)
            remaining.difference_update(available)
        info(f"Applying log rotation to {len(order)} running services; stopped services are preserved.")
        for service in order:
            previous, desired, target_image = pending[service]
            current = inspect([previous["Id"]])[0]
            if current["State"]["Status"] != "running":
                raise RuntimeError(f"{service}: state changed during rollout; refusing to start it.")
            was_healthy = previous["State"].get("Health", {}).get("Status") == "healthy"
            info(f"Recreating {service} with pinned image {target_image} and bounded logs.")
            subprocess.run([*command, "up", "-d", "--no-deps", "--no-build", "--pull", "never",
                            "--force-recreate", service], check=True)
            ready(command, service, target_image, desired, was_healthy)
            info(f"Verified {service}: {desired['Config']['max-file']} log files, "
                 f"{desired['Config']['max-size']} bytes each.")

    if unavailable:
        raise RuntimeError("Rotation applied to available images; still deferred: "
                           + ", ".join(sorted(unavailable)))


def main():
    arguments = sys.argv[1:]
    if arguments[:1] == ["--"]:
        arguments = arguments[1:]
    allow_current_images = arguments[:1] == ["--allow-current-images"]
    if allow_current_images:
        arguments = arguments[1:]
    if arguments[:2] != ["docker", "compose"]:
        raise RuntimeError("Expected the Olympus Docker Compose command.")
    apply(arguments, allow_current_images)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        sys.exit(1)
