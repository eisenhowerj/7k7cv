#!/usr/bin/env python3
"""CDK app entry point for the 7K7 static-site infrastructure."""
from pathlib import Path
from typing import Any

import tomllib

import aws_cdk as cdk

from stacks.github_oidc_stack import GitHubOidcStack
from stacks.static_site_stack import StaticSiteStack


def _load_cdk_config() -> dict[str, Any]:
    """Load optional CDK defaults from infra/config.toml."""
    config_path = Path(__file__).with_name("config.toml")
    if not config_path.exists():
        return {}

    with config_path.open("rb") as f:
        parsed = tomllib.load(f)

    cdk_config = parsed.get("cdk", {})
    if not isinstance(cdk_config, dict):
        raise ValueError("[cdk] section in config.toml must be a table")

    # Ignore unset string values so optional keys can remain blank.
    return {
        key: value
        for key, value in cdk_config.items()
        if not (isinstance(value, str) and value.strip() == "")
    }

app = cdk.App()

for key, value in _load_cdk_config().items():
    # Command-line -c values should always win over file defaults.
    if app.node.try_get_context(key) is None:
        app.node.set_context(key, value)

env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "us-east-1",
)

# Bootstrap stack: OIDC provider + GitHub Actions IAM roles.
# Deploy this once per account (in a single chosen region) before the first site deploy.
GitHubOidcStack(app, "SevenK7GitHubOidc", env=env)

StaticSiteStack(app, "SevenK7StaticSite", env=env)

app.synth()
