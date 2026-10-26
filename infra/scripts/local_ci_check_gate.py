"""Validate pull-request identity before any local CI result may be published."""

import re

SHA = re.compile(r"[0-9a-f]{40}\Z")


def verify_pr_head(pr: dict, number: int, repo: str, sha: str) -> None:
    """Fail closed unless the remote PR still targets this exact commit."""
    try:
        head = pr["head"]
        base = pr["base"]
        head_repo = head["repo"]
        base_repo = base["repo"]
        valid = (
            type(number) is int
            and number > 0
            and isinstance(sha, str)
            and SHA.fullmatch(sha) is not None
            and pr["number"] == number
            and pr["state"] == "open"
            and head["sha"] == sha
            and head_repo["full_name"] == repo
            and base_repo["full_name"] == repo
            and type(head_repo["id"]) is int
            and head_repo["id"] == base_repo["id"]
            and base["ref"] == "main"
        )
    except (KeyError, TypeError, AttributeError):
        valid = False
    if not valid:
        raise ValueError("pull request head does not match the checked commit")
