#!/usr/bin/env python3
"""
Scan every Docker context (or a hard‑coded list of base_url strings) and report
containers whose running image digest differs from the upstream tag—without
any multithreading.  Requires: pip install 'docker[ssh]'
"""
import subprocess, json, docker, sys
from typing import List

def list_contexts() -> List[str]:
    """Return the names of all local Docker contexts except 'default'."""
    out = subprocess.check_output(
        ["docker", "context", "ls", "--format", "{{.Name}}"]
    ).decode().splitlines()
    return [c for c in out if c]            # keep every defined context

def host_from_context(ctx: str) -> str:
    """Extract the endpoint URI stored in a context (SSH or TCP)."""
    raw = subprocess.check_output(
        ["docker", "context", "inspect", ctx,
         "--format", "{{json .Endpoints.docker.Host}}"]
    ).decode()
    return json.loads(raw)                  # e.g. 'ssh://user@host'

def check_one_client(client: docker.DockerClient, label: str):
    """Print a line for every container whose image is stale."""
    for ctr in client.containers.list():
        img = ctr.image
        local_id = img.id.split(":", 1)[1]         # sha256 w/o prefix
        tag = (img.tags or ["<none>:<none>"])[0]

        # ask registry for the current digest of <repo>:<tag>
        remote_digest = client.images.get_registry_data(tag).id   # :contentReference[oaicite:2]{index=2}
        remote_id = remote_digest.split(":", 1)[1]

        if local_id != remote_id:
            print(f"[update] {label}:{ctr.name} → {tag} "
                  f"(local {local_id[:12]}… → remote {remote_id[:12]}…)")

def main():
    print("Scanning Docker contexts in sequence …")
    for ctx in list_contexts():                    # sequential loop
        try:
            host = host_from_context(ctx)          # :contentReference[oaicite:3]{index=3}
            client = docker.DockerClient(base_url=host, timeout=20)
        except Exception as e:
            print(f"[error] Context {ctx}: {e}", file=sys.stderr)
            continue

        print(f"\n== {ctx} ({host}) ==")
        check_one_client(client, ctx)

if __name__ == "__main__":
    main()

