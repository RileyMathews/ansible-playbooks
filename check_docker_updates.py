import docker
import requests
from urllib.parse import urlparse
import time

REMOTE_HOSTS = [
    "ssh://riley@enterprise",
    "ssh://riley@mealie",
    "ssh://riley@vaultwarden",
    "ssh://riley@homeassistant",
    "ssh://riley@holodeck"
]

HEADERS = {
    "Accept": "application/vnd.docker.distribution.manifest.v2+json"
}

DOCKER_HUB_TOKEN_CACHE = {}
GHCR_TOKEN_CACHE = {}
checked_images = {}

def get_remote_client(host_uri):
    return docker.DockerClient(base_url=host_uri)

def get_local_digest(container):
    repo_digests = container.image.attrs.get("RepoDigests", [])
    if not repo_digests:
        print("Could not find digest")
        return None
    return repo_digests[0].split('@')[1]

def parse_image_tag(image_name):
    if ':' not in image_name:
        image_name += ":latest"
    repo, tag = image_name.rsplit(':', 1)
    return repo, tag

def get_registry(image):
    if image.startswith("ghcr.io/"):
        return "ghcr"
    else:
        return "dockerhub"

def get_dockerhub_token(image):
    if image in DOCKER_HUB_TOKEN_CACHE:
        return DOCKER_HUB_TOKEN_CACHE[image]
    url = f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:{image}:pull"
    r = requests.get(url)
    r.raise_for_status()
    token = r.json()['token']
    DOCKER_HUB_TOKEN_CACHE[image] = token
    return token

def get_ghcr_token(image):
    if image.startswith("ghcr.io/"):
        image = image.replace("ghcr.io/", "", 1)
    if image in GHCR_TOKEN_CACHE:
        return GHCR_TOKEN_CACHE[image]
    url = f"https://ghcr.io/token?scope=repository:{image}:pull"
    r = requests.get(url)
    r.raise_for_status()
    token = r.json()['token']
    GHCR_TOKEN_CACHE[image] = token
    return token


def get_remote_digest_dockerhub(image, tag='latest'):
    normalized = normalize_dockerhub_image(image)
    token = get_dockerhub_token(normalized)
    headers = HEADERS.copy()
    headers['Authorization'] = f"Bearer {token}"
    url = f"https://registry-1.docker.io/v2/{normalized}/manifests/{tag}"
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.headers['Docker-Content-Digest']

def get_remote_digest_ghcr(image, tag='latest'):
    # Remove leading registry domain
    if image.startswith("ghcr.io/"):
        image = image.replace("ghcr.io/", "", 1)

    token = get_ghcr_token(image)
    headers = HEADERS.copy()
    headers['Authorization'] = f"Bearer {token}"
    url = f"https://ghcr.io/v2/{image}/manifests/{tag}"
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.headers['Docker-Content-Digest']


def normalize_dockerhub_image(image):
    if '/' not in image:
        return f"library/{image}"
    return image

def check_container_update(client, container):
    tags = container.image.tags
    if not tags:
        return
    image_tag = tags[0]
    repo, tag = parse_image_tag(image_tag)

    if tag != "latest":
        print(f"[SKIP] {image_tag} on {client.api.base_url} is not tagged as latest")
        return

    cache_key = f"{repo}:{tag}"
    if cache_key in checked_images:
        result = checked_images[cache_key]
        print(f"[CACHE] {image_tag} on {client.api.base_url}: {result}")
        return

    try:
        local_digest = get_local_digest(container)
        if not local_digest:
            raise Exception("No RepoDigest found.")

        registry = get_registry(repo)
        if registry == "dockerhub":
            remote_digest = get_remote_digest_dockerhub(repo, tag)
        elif registry == "ghcr":
            remote_digest = get_remote_digest_ghcr(repo, tag)
        else:
            raise Exception(f"Unsupported registry for image: {repo}")

        if local_digest != remote_digest:
            msg = f"[UPDATE] {image_tag} on {client.api.base_url} is outdated"
        else:
            msg = f"[OK] {image_tag} on {client.api.base_url} is up-to-date"

        checked_images[cache_key] = msg
        print(msg)

    except Exception as e:
        print(f"[ERROR] {image_tag} on {client.api.base_url}: {e}")
        checked_images[cache_key] = None

def main():
    for host in REMOTE_HOSTS:
        print(host)
        try:
            client = get_remote_client(host)
            for container in client.containers.list():
                check_container_update(client, container)
        except Exception as e:
            print(f"[ERROR] Could not connect to {host}: {e}")

if __name__ == "__main__":
    main()

