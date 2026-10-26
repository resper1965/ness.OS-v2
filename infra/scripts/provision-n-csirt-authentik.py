#!/usr/bin/env python3
"""Idempotently provision the n.csirt OIDC integration in authentik."""

from __future__ import annotations

import json
import os
import pathlib
import secrets
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request


BASE_URL = os.environ.get("AUTHENTIK_URL", "https://sso.ness.com.br").rstrip("/")
PUBLIC_ORIGIN = os.environ.get(
    "NCSIRT_PUBLIC_ORIGIN", "https://ncsirt.ness.com.br"
).rstrip("/")
TOKEN_FILE = pathlib.Path(
    os.environ.get(
        "AUTHENTIK_TOKEN_FILE", "/home/resper/.config/ness/authentik-token"
    )
)
CLIENT_SECRET_FILE = pathlib.Path(
    os.environ.get(
        "NCSIRT_CLIENT_SECRET_FILE",
        "/home/resper/.config/ness/n-csirt-client-secret",
    )
)

GROUP_NAMES = ("n-csirt-access", "platform_admin", "soc", "gestao", "usuarios")
REDIRECT_URIS = (
    {
        "matching_mode": "strict",
        "url": f"{PUBLIC_ORIGIN}/auth/oidc/callback",
        "redirect_uri_type": "authorization",
    },
    {
        "matching_mode": "strict",
        "url": f"{PUBLIC_ORIGIN}/auth/callback",
        "redirect_uri_type": "authorization",
    },
    {
        "matching_mode": "strict",
        "url": f"{PUBLIC_ORIGIN}/auth/logout/callback",
        "redirect_uri_type": "logout",
    },
    # Compatibilidade temporaria de rollback. Remover depois da validacao do
    # dominio canonico em producao.
    {
        "matching_mode": "strict",
        "url": "https://alupar-ctir-gov.pages.dev/auth/oidc/callback",
        "redirect_uri_type": "authorization",
    },
    {
        "matching_mode": "strict",
        "url": "https://alupar-ctir-gov.pages.dev/auth/callback",
        "redirect_uri_type": "authorization",
    },
    {
        "matching_mode": "strict",
        "url": "https://alupar-ctir-gov.pages.dev/auth/logout/callback",
        "redirect_uri_type": "logout",
    },
)

NCSIRT_SCOPE_EXPRESSION = """return {
    \"groups\": [group.name for group in request.user.ak_groups.all()],
}
"""

ACCESS_AND_PKCE_EXPRESSION = """# n.csirt mandatory access gate and PKCE S256 enforcement.
if not ak_is_group_member(request.user, name=\"n-csirt-access\"):
    return False

grant_type = request.context.get(\"oauth_grant_type\")
if grant_type != \"authorization_code\":
    return True

# Authorization endpoint: require a challenge and explicitly require S256.
if \"oauth_code_challenge_method\" in request.context:
    return (
        bool(request.context.get(\"oauth_code_challenge\"))
        and request.context.get(\"oauth_code_challenge_method\") == \"S256\"
    )

# Token endpoint: require the verifier corresponding to the stored challenge.
if \"oauth_code_verifier\" in request.context:
    return bool(request.context.get(\"oauth_code_verifier\"))

return False
"""


def redact(value: str, token: str) -> str:
    value = value.replace(token, "<redacted-token>")
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return value[:1000]
    if isinstance(parsed, dict) and "client_secret" in parsed:
        parsed["client_secret"] = "<redacted-client-secret>"
    return json.dumps(parsed, ensure_ascii=False)[:2000]


class AuthentikAPI:
    def __init__(self, token: str):
        self.token = token
        self.context = ssl.create_default_context()

    def request(self, method: str, path: str, payload=None, params=None):
        url = f"{BASE_URL}/api/v3{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params, doseq=True)
        data = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, context=self.context, timeout=45) as response:
                body = response.read()
                return json.loads(body) if body else None
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", "replace")
            raise RuntimeError(
                f"{method} {path} failed with HTTP {error.code}: "
                f"{redact(body, self.token)}"
            ) from error

    def list(self, path: str, **params):
        params.setdefault("page_size", 100)
        return self.request("GET", path, params=params).get("results", [])

    def exactly_one(self, path: str, label: str, **params):
        results = self.list(path, **params)
        if len(results) != 1:
            raise RuntimeError(f"Expected one {label}, found {len(results)}")
        return results[0]

    def upsert_by_filter(
        self, *, collection: str, detail: str, filters: dict, payload: dict, key: str, label: str
    ):
        existing = self.list(collection, **filters)
        if len(existing) > 1:
            raise RuntimeError(f"Multiple {label} objects match {filters}")
        if existing:
            obj = self.request("PATCH", detail.format(key=existing[0][key]), payload)
            print(f"updated {label}")
            return obj, False
        obj = self.request("POST", collection, payload)
        print(f"created {label}")
        return obj, True


def store_client_secret(secret: str) -> None:
    if not secret:
        raise RuntimeError("authentik did not return a generated client secret")
    CLIENT_SECRET_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(CLIENT_SECRET_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, secret.encode("utf-8"))
    finally:
        os.close(fd)
    os.chmod(CLIENT_SECRET_FILE, 0o600)


def main() -> int:
    token = TOKEN_FILE.read_text(encoding="utf-8-sig").strip()
    if len(token) < 20:
        raise RuntimeError(f"Token file is empty or invalid: {TOKEN_FILE}")
    api = AuthentikAPI(token)

    me = api.request("GET", "/core/users/me/")
    if not me:
        raise RuntimeError("Token authentication failed")
    print("token authentication OK")

    groups = {}
    for name in GROUP_NAMES:
        group, _ = api.upsert_by_filter(
            collection="/core/groups/",
            detail="/core/groups/{key}/",
            filters={"name": name},
            payload={"name": name, "is_superuser": False},
            key="pk",
            label=f"group {name}",
        )
        groups[name] = group

    scope_mappings = {}
    for scope_name in ("openid", "profile", "email"):
        scope_mappings[scope_name] = api.exactly_one(
            "/propertymappings/provider/scope/",
            f"scope mapping {scope_name}",
            scope_name=scope_name,
        )

    ncsirt_scope, _ = api.upsert_by_filter(
        collection="/propertymappings/provider/scope/",
        detail="/propertymappings/provider/scope/{key}/",
        filters={"scope_name": "ncsirt"},
        payload={
            "name": "n.csirt roles and groups",
            "scope_name": "ncsirt",
            "description": "Expose Authentik groups used by n.csirt RBAC.",
            "expression": NCSIRT_SCOPE_EXPRESSION,
        },
        key="pk",
        label="scope ncsirt",
    )
    scope_mappings["ncsirt"] = ncsirt_scope

    authorization_flow = api.exactly_one(
        "/flows/instances/",
        "default authorization flow",
        slug="default-provider-authorization-implicit-consent",
    )
    invalidation_flow = api.exactly_one(
        "/flows/instances/",
        "default invalidation flow",
        slug="default-provider-invalidation-flow",
    )
    signing_key = api.exactly_one(
        "/crypto/certificatekeypairs/",
        "default signing key",
        name="authentik Self-signed Certificate",
    )

    provider_payload = {
        "name": "n-csirt-oidc",
        "authorization_flow": authorization_flow["pk"],
        "invalidation_flow": invalidation_flow["pk"],
        "property_mappings": [
            scope_mappings[name]["pk"] for name in ("openid", "profile", "email", "ncsirt")
        ],
        "client_type": "confidential",
        "grant_types": ["authorization_code", "refresh_token"],
        "client_id": "n-csirt",
        "include_claims_in_id_token": True,
        "signing_key": signing_key["pk"],
        "redirect_uris": list(REDIRECT_URIS),
        "sub_mode": "hashed_user_id",
        "issuer_mode": "per_provider",
    }
    existing_provider = api.list("/providers/oauth2/", name="n-csirt-oidc")
    if len(existing_provider) > 1:
        raise RuntimeError("Multiple n-csirt-oidc providers found")
    if existing_provider:
        provider = api.request(
            "PATCH", f"/providers/oauth2/{existing_provider[0]['pk']}/", provider_payload
        )
        print("updated provider n-csirt-oidc (client secret preserved)")
    else:
        provider_payload["client_secret"] = secrets.token_urlsafe(48)
        provider = api.request("POST", "/providers/oauth2/", provider_payload)
        store_client_secret(provider_payload["client_secret"])
        provider_payload["client_secret"] = "<redacted>"
        print(f"created provider n-csirt-oidc; client secret stored at {CLIENT_SECRET_FILE}")

    application_payload = {
        "name": "n.csirt",
        "slug": "n-csirt",
        "provider": provider["pk"],
        "meta_launch_url": f"{PUBLIC_ORIGIN}/auth/login",
        "policy_engine_mode": "any",
    }
    try:
        application = api.request("GET", "/core/applications/n-csirt/")
    except RuntimeError as error:
        if "HTTP 404" not in str(error):
            raise
        application = None
    if application:
        application = api.request(
            "PATCH", "/core/applications/n-csirt/", application_payload
        )
        print("updated application n.csirt")
    else:
        application = api.request("POST", "/core/applications/", application_payload)
        print("created application n.csirt")

    policy, _ = api.upsert_by_filter(
        collection="/policies/expression/",
        detail="/policies/expression/{key}/",
        filters={"name": "n-csirt-access-and-pkce-s256"},
        payload={
            "name": "n-csirt-access-and-pkce-s256",
            "execution_logging": True,
            "expression": ACCESS_AND_PKCE_EXPRESSION,
        },
        key="pk",
        label="access and PKCE policy",
    )

    bindings = api.list("/policies/bindings/", target=application["pk"])
    matching = [item for item in bindings if item.get("policy") == policy["pk"]]
    binding_payload = {
        "policy": policy["pk"],
        "target": application["pk"],
        "order": 0,
        "enabled": True,
        "negate": False,
        "timeout": 30,
        "failure_result": False,
    }
    if matching:
        api.request("PATCH", f"/policies/bindings/{matching[0]['pk']}/", binding_payload)
        print("updated application policy binding")
    else:
        api.request("POST", "/policies/bindings/", binding_payload)
        print("created application policy binding")

    print("provisioning complete")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
