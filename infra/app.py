#!/usr/bin/env python3
"""CDK app entry point for the 7K7 static-site infrastructure."""
import aws_cdk as cdk

from stacks.static_site_stack import StaticSiteStack

app = cdk.App()

StaticSiteStack(
    app,
    "SevenK7StaticSite",
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-east-1",
    ),
)

app.synth()
