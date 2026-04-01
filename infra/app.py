#!/usr/bin/env python3
"""CDK app entry point for the 7K7 static-site infrastructure."""
import aws_cdk as cdk

from stacks.github_oidc_stack import GitHubOidcStack
from stacks.static_site_stack import StaticSiteStack

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "us-east-1",
)

# Bootstrap stack: OIDC provider + GitHub Actions IAM roles.
# Deploy this once per account (in a single chosen region) before the first site deploy.
GitHubOidcStack(app, "SevenK7GitHubOidc", env=env)

StaticSiteStack(app, "SevenK7StaticSite", env=env)

app.synth()
