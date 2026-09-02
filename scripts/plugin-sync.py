#!/usr/bin/env python3
"""Create and maintain GitHub pull mirrors on Forgejo."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


FORGEJO_URL = "https://git.maciejurban.dev"
FORGEJO_OWNER = "BlankTiger"
GITHUB_OWNER = "blanktiger"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
HOME_CONFIG_REPOSITORY = PROJECT_ROOT / "forgejo/git/repositories/blanktiger/homecfg.git"


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def run_command(command: Sequence[str], *, environment: Mapping[str, str] | None = None) -> CommandResult:
    result = subprocess.run(
        command,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    return CommandResult(result.returncode, result.stdout, result.stderr)


def required_environment(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def github_environment(token: str) -> dict[str, str]:
    environment = os.environ.copy()
    environment["GH_TOKEN"] = token
    return environment


def github_repositories(token: str) -> set[str]:
    result = run_command(
        [
            "gh",
            "repo",
            "list",
            GITHUB_OWNER,
            "--limit",
            "1000",
            "--json",
            "nameWithOwner",
            "--jq",
            ".[].nameWithOwner",
        ],
        environment=github_environment(token),
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "failed to list GitHub repositories")
    return {line for line in result.stdout.splitlines() if line}


def repositories_from_homecfg() -> set[str]:
    result = run_command(
        [
            "git",
            f"--git-dir={HOME_CONFIG_REPOSITORY}",
            "grep",
            "-rhoP",
            r'''["'][a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+["']''',
            "HEAD",
        ]
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.strip() or "failed to inspect home configuration")

    repositories: set[str] = set()
    for line in result.stdout.splitlines():
        repositories.update(part.strip("\"'") for part in line.split())
    return repositories


def github_repository(token: str, repository: str) -> dict[str, Any] | None:
    result = run_command(
        ["gh", "api", f"repos/{repository}"],
        environment=github_environment(token),
    )
    if result.returncode != 0:
        print(f"{repository} does not exist or is not accessible")
        return None
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise RuntimeError(f"unexpected GitHub response for {repository}")
    return value


def forgejo_request(
    forgejo_token: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int, str]:
    command = [
        "curl",
        "--silent",
        "--show-error",
        "--connect-timeout",
        "15",
        "--max-time",
        "300",
        "-X",
        method,
        "-H",
        f"Authorization: token {forgejo_token}",
        f"{FORGEJO_URL}{path}",
    ]
    if payload is not None:
        command.extend(["-H", "Content-Type: application/json", "--data", json.dumps(payload)])

    result = run_command(command)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"Forgejo request failed: {path}")
    body, separator, status = result.stdout.rpartition("\n")
    if not separator:
        raise RuntimeError(f"Forgejo returned no HTTP status: {path}")
    return int(status), body


def create_forgejo_user(owner: str, password: str, container: str) -> None:
    result = run_command(
        [
            "sudo",
            "docker",
            "exec",
            "--user",
            "git",
            container,
            "forgejo",
            "admin",
            "user",
            "create",
            "--username",
            owner,
            "--email",
            f"{owner}@local",
            "--password",
            password,
            "--must-change-password=false",
        ]
    )
    if result.returncode != 0:
        print(f"Forgejo user {owner} already exists or could not be created")


def target_owner(source_owner: str) -> str:
    if source_owner.casefold() == GITHUB_OWNER:
        return FORGEJO_OWNER
    return source_owner


def migrate_repository(
    repository: str,
    source: dict[str, Any],
    forgejo_token: str,
    github_token: str,
    fake_user_password: str,
    container: str,
) -> None:
    source_owner, name = repository.split("/", 1)
    owner = target_owner(source_owner)
    private = bool(source.get("private", False))
    path = f"/api/v1/repos/{owner}/{name}"
    status, _ = forgejo_request(forgejo_token, "GET", path)

    if status == 200:
        if private:
            forgejo_request(forgejo_token, "PATCH", path, {"private": True})
            print(f"made {owner}/{name} private")
        print(f"{owner}/{name} already exists on Forgejo")
        return
    if status != 404:
        print(f"Could not inspect {owner}/{name} on Forgejo (HTTP {status})")
        return

    create_forgejo_user(owner, fake_user_password, container)
    payload = {
        "clone_addr": f"https://github.com/{repository}.git",
        "repo_name": name,
        "repo_owner": owner,
        "mirror": True,
        "private": private,
        "service": "github",
        "auth_token": github_token,
    }
    status, body = forgejo_request(forgejo_token, "POST", "/api/v1/repos/migrate", payload)
    if 200 <= status < 300:
        print(f"Created {owner}/{name} mirror")
    else:
        print(f"Failed to create {owner}/{name} mirror (HTTP {status}): {body}")


def main() -> int:
    forgejo_token = required_environment("FORGEJO_TOKEN")
    github_token = required_environment("GITHUB_TOKEN")
    fake_user_password = required_environment("FAKE_USER_PASS")
    container_result = run_command(["sudo", "docker", "ps", "-qf", "name=forgejo"])
    container = container_result.stdout.strip()
    if container_result.returncode != 0 or not container:
        raise RuntimeError("Forgejo container is not running")

    repositories = repositories_from_homecfg()
    repositories.update({"ghostty-org/ghostty", "neovim/neovim", "hyprwm/Hyprland"})
    repositories.update(github_repositories(github_token))

    for repository in sorted(repositories):
        source = github_repository(github_token, repository)
        if source is not None:
            migrate_repository(
                repository,
                source,
                forgejo_token,
                github_token,
                fake_user_password,
                container,
            )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, json.JSONDecodeError, ValueError) as error:
        print(f"mirror sync failed: {error}", file=sys.stderr)
        sys.exit(1)
