"""CDK stack that bootstraps GitHub Actions OIDC authentication for the
7K7 repository.

What it provisions
------------------
1. An IAM OIDC Identity Provider for ``token.actions.githubusercontent.com``
   (skipped when one already exists in the account — use ``existing_oidc_arn``
   to import it).
2. A *deploy* IAM role assumed by the ``deploy.yml`` workflow on pushes to
   ``main``.  The role has the least-privilege permissions needed to run
   ``cdk deploy`` and sync static assets to S3.
3. A *readonly* IAM role assumed by the ``pr.yml`` workflow on pull requests.
   The role is limited to read-only / describe operations required for
   ``cdk diff``.

CDK context keys
----------------
github_owner   : str  – GitHub owner (organisation or username)
                        (default: ``eisenhowerj``)
github_repo    : str  – Repository name (default: ``7k7cv``)
existing_oidc_arn : str  – ARN of an existing OIDC provider to import instead
                           of creating a new one (optional).
"""
from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import (
    CfnOutput,
    Stack,
    aws_iam as iam,
)
from constructs import Construct

# Thumbprint list for token.actions.githubusercontent.com
# See https://docs.github.com/en/actions/security-for-github-actions/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services
_GITHUB_THUMBPRINTS = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd",
]

_GITHUB_OIDC_URL = "https://token.actions.githubusercontent.com"


class GitHubOidcStack(Stack):
    """Provisions the GitHub Actions OIDC provider and deploy/readonly IAM roles."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs: object) -> None:
        super().__init__(scope, construct_id, **kwargs)

        github_owner: str = self.node.try_get_context("github_owner") or "eisenhowerj"
        github_repo: str = self.node.try_get_context("github_repo") or "7k7cv"
        existing_oidc_arn: str | None = self.node.try_get_context("existing_oidc_arn")

        # ── OIDC Identity Provider ───────────────────────────────────────────
        if existing_oidc_arn:
            oidc_provider = iam.OpenIdConnectProvider.from_open_id_connect_provider_arn(
                self,
                "GitHubOidcProvider",
                existing_oidc_arn,
            )
        else:
            oidc_provider = iam.OpenIdConnectProvider(
                self,
                "GitHubOidcProvider",
                url=_GITHUB_OIDC_URL,
                client_ids=["sts.amazonaws.com"],
                thumbprints=_GITHUB_THUMBPRINTS,
            )

        # Shared principal that validates the OIDC token came from this repo
        def _github_principal(subject_condition: str) -> iam.WebIdentityPrincipal:
            return iam.WebIdentityPrincipal(
                oidc_provider.open_id_connect_provider_arn,
                conditions={
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                        "token.actions.githubusercontent.com:sub": subject_condition,
                    }
                },
            )

        # ── Deploy role (used by deploy.yml on push to main) ─────────────────
        deploy_role = iam.Role(
            self,
            "DeployRole",
            role_name=f"github-actions-deploy-{github_repo}",
            assumed_by=_github_principal(
                f"repo:{github_owner}/{github_repo}:ref:refs/heads/main"
            ),
            description=(
                "Assumed by GitHub Actions (deploy.yml) to run cdk deploy "
                "and sync static assets to S3."
            ),
            max_session_duration=cdk.Duration.hours(1),
        )

        # CloudFormation — list actions require account-wide wildcard resource
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                sid="CloudFormationList",
                actions=["cloudformation:ListStacks"],
                resources=["*"],
            )
        )

        # CloudFormation — stack-scoped management actions
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                sid="CloudFormationDeploy",
                actions=[
                    "cloudformation:CreateStack",
                    "cloudformation:UpdateStack",
                    "cloudformation:DeleteStack",
                    "cloudformation:DescribeStacks",
                    "cloudformation:DescribeStackEvents",
                    "cloudformation:DescribeStackResources",
                    "cloudformation:GetTemplate",
                    "cloudformation:GetTemplateSummary",
                    "cloudformation:ValidateTemplate",
                    "cloudformation:ListStackResources",
                    "cloudformation:SetStackPolicy",
                    "cloudformation:CreateChangeSet",
                    "cloudformation:ExecuteChangeSet",
                    "cloudformation:DescribeChangeSet",
                    "cloudformation:DeleteChangeSet",
                    "cloudformation:TagResource",
                    "cloudformation:UntagResource",
                ],
                resources=[
                    # Project stacks
                    f"arn:aws:cloudformation:*:*:stack/SevenK7*/*",
                    # CDK bootstrap stack
                    "arn:aws:cloudformation:*:*:stack/CDKToolkit/*",
                ],
            )
        )

        # S3 — CDK bootstrap bucket (cdk-*) and site bucket (*-site)
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                sid="S3CdkBootstrap",
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                    "s3:GetBucketPolicy",
                    "s3:PutBucketPolicy",
                    "s3:GetBucketVersioning",
                    "s3:PutBucketVersioning",
                    "s3:GetEncryptionConfiguration",
                    "s3:PutEncryptionConfiguration",
                    "s3:CreateBucket",
                    "s3:DeleteBucket",
                    "s3:PutBucketPublicAccessBlock",
                    "s3:GetBucketPublicAccessBlock",
                    "s3:PutBucketTagging",
                    "s3:GetBucketTagging",
                ],
                resources=[
                    "arn:aws:s3:::cdk-*",
                    "arn:aws:s3:::cdk-*/*",
                    "arn:aws:s3:::*-site",
                    "arn:aws:s3:::*-site/*",
                ],
            )
        )

        # CloudFront — distribution management and cache invalidations
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                sid="CloudFrontDeploy",
                actions=[
                    "cloudfront:CreateDistribution",
                    "cloudfront:UpdateDistribution",
                    "cloudfront:DeleteDistribution",
                    "cloudfront:GetDistribution",
                    "cloudfront:GetDistributionConfig",
                    "cloudfront:ListDistributions",
                    "cloudfront:CreateInvalidation",
                    "cloudfront:GetInvalidation",
                    "cloudfront:ListInvalidations",
                    "cloudfront:TagResource",
                    "cloudfront:UntagResource",
                    "cloudfront:CreateOriginAccessControl",
                    "cloudfront:GetOriginAccessControl",
                    "cloudfront:DeleteOriginAccessControl",
                    "cloudfront:UpdateOriginAccessControl",
                    "cloudfront:ListOriginAccessControls",
                ],
                resources=["*"],
            )
        )

        # ACM — certificate management for the site domain
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                sid="AcmDeploy",
                actions=[
                    "acm:DescribeCertificate",
                    "acm:ListCertificates",
                    "acm:RequestCertificate",
                    "acm:DeleteCertificate",
                    "acm:AddTagsToCertificate",
                    "acm:ListTagsForCertificate",
                ],
                resources=["*"],
            )
        )

        # Route 53 — DNS record management
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                sid="Route53Deploy",
                actions=[
                    "route53:GetHostedZone",
                    "route53:ListHostedZones",
                    "route53:ListHostedZonesByName",
                    "route53:ChangeResourceRecordSets",
                    "route53:GetChange",
                    "route53:ListResourceRecordSets",
                ],
                resources=["*"],
            )
        )

        # SSM — CDK bootstrap reads/writes parameter store under /cdk-bootstrap/
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                sid="SsmCdkBootstrap",
                actions=[
                    "ssm:GetParameter",
                    "ssm:GetParameters",
                    "ssm:PutParameter",
                    "ssm:DeleteParameter",
                    "ssm:AddTagsToResource",
                ],
                resources=[
                    "arn:aws:ssm:*:*:parameter/cdk-bootstrap/*",
                ],
            )
        )

        # STS — identity check (requires wildcard) and CDK assume-role (scoped to cdk-* roles)
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                sid="StsGetCallerIdentity",
                actions=["sts:GetCallerIdentity"],
                resources=["*"],
            )
        )
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                sid="StsAssumeRoleCdk",
                actions=["sts:AssumeRole"],
                resources=[
                    "arn:aws:iam::*:role/cdk-*",
                ],
            )
        )

        # IAM — list actions require account-wide wildcard resource
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                sid="IamList",
                actions=["iam:ListRoles"],
                resources=["*"],
            )
        )

        # IAM — scoped to CDK execution roles and SevenK7* roles/policies
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                sid="IamCdkBootstrap",
                actions=[
                    "iam:CreateRole",
                    "iam:DeleteRole",
                    "iam:GetRole",
                    "iam:PassRole",
                    "iam:AttachRolePolicy",
                    "iam:DetachRolePolicy",
                    "iam:PutRolePolicy",
                    "iam:DeleteRolePolicy",
                    "iam:GetRolePolicy",
                    "iam:TagRole",
                    "iam:UntagRole",
                    "iam:UpdateAssumeRolePolicy",
                    "iam:CreatePolicy",
                    "iam:DeletePolicy",
                    "iam:GetPolicy",
                    "iam:GetPolicyVersion",
                    "iam:ListPolicyVersions",
                    "iam:CreatePolicyVersion",
                    "iam:DeletePolicyVersion",
                ],
                resources=[
                    "arn:aws:iam::*:role/cdk-*",
                    "arn:aws:iam::*:role/SevenK7*",
                    f"arn:aws:iam::*:role/github-actions-*-{github_repo}",
                    "arn:aws:iam::*:policy/cdk-*",
                    "arn:aws:iam::*:policy/SevenK7*",
                ],
            )
        )

        # ── Readonly role (used by pr.yml on pull requests) ──────────────────
        readonly_role = iam.Role(
            self,
            "ReadonlyRole",
            role_name=f"github-actions-readonly-{github_repo}",
            assumed_by=_github_principal(
                f"repo:{github_owner}/{github_repo}:pull_request"
            ),
            description=(
                "Assumed by GitHub Actions (pr.yml) for read-only operations "
                "such as cdk diff and CDK synth."
            ),
            max_session_duration=cdk.Duration.hours(1),
        )

        # CloudFormation — list actions require account-wide wildcard resource
        readonly_role.add_to_policy(
            iam.PolicyStatement(
                sid="ReadonlyCloudFormationList",
                actions=["cloudformation:ListStacks"],
                resources=["*"],
            )
        )

        readonly_role.add_to_policy(
            iam.PolicyStatement(
                sid="ReadonlyCdkDiff",
                actions=[
                    # CloudFormation (cdk diff reads current stack state)
                    "cloudformation:DescribeStacks",
                    "cloudformation:DescribeStackResources",
                    "cloudformation:DescribeStackEvents",
                    "cloudformation:GetTemplate",
                    "cloudformation:ListStackResources",
                    "cloudformation:GetStackPolicy",
                ],
                resources=[
                    f"arn:aws:cloudformation:*:*:stack/SevenK7*/*",
                    "arn:aws:cloudformation:*:*:stack/CDKToolkit/*",
                ],
            )
        )

        readonly_role.add_to_policy(
            iam.PolicyStatement(
                sid="ReadonlyS3",
                actions=[
                    "s3:GetObject",
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                    "s3:GetBucketPolicy",
                    "s3:GetEncryptionConfiguration",
                    "s3:GetBucketVersioning",
                    "s3:GetBucketTagging",
                    "s3:GetBucketPublicAccessBlock",
                ],
                resources=[
                    "arn:aws:s3:::cdk-*",
                    "arn:aws:s3:::cdk-*/*",
                    "arn:aws:s3:::*-site",
                    "arn:aws:s3:::*-site/*",
                ],
            )
        )

        readonly_role.add_to_policy(
            iam.PolicyStatement(
                sid="ReadonlyCloudFront",
                actions=[
                    "cloudfront:GetDistribution",
                    "cloudfront:GetDistributionConfig",
                    "cloudfront:ListDistributions",
                    "cloudfront:GetOriginAccessControl",
                    "cloudfront:ListOriginAccessControls",
                ],
                resources=["*"],
            )
        )

        readonly_role.add_to_policy(
            iam.PolicyStatement(
                sid="ReadonlyAcmRoute53",
                actions=[
                    "acm:DescribeCertificate",
                    "acm:ListCertificates",
                    "acm:ListTagsForCertificate",
                    "route53:GetHostedZone",
                    "route53:ListHostedZones",
                    "route53:ListResourceRecordSets",
                ],
                resources=["*"],
            )
        )

        readonly_role.add_to_policy(
            iam.PolicyStatement(
                sid="ReadonlySsmCdkBootstrap",
                actions=[
                    "ssm:GetParameter",
                    "ssm:GetParameters",
                ],
                resources=[
                    "arn:aws:ssm:*:*:parameter/cdk-bootstrap/*",
                ],
            )
        )

        readonly_role.add_to_policy(
            iam.PolicyStatement(
                sid="ReadonlySts",
                actions=["sts:GetCallerIdentity"],
                resources=["*"],
            )
        )

        # IAM — list actions require account-wide wildcard resource
        readonly_role.add_to_policy(
            iam.PolicyStatement(
                sid="ReadonlyIamList",
                actions=["iam:ListRoles"],
                resources=["*"],
            )
        )

        readonly_role.add_to_policy(
            iam.PolicyStatement(
                sid="ReadonlyIam",
                actions=[
                    "iam:GetRole",
                    "iam:GetPolicy",
                    "iam:GetPolicyVersion",
                    "iam:ListPolicyVersions",
                    "iam:GetRolePolicy",
                    "iam:ListRolePolicies",
                    "iam:ListAttachedRolePolicies",
                ],
                resources=[
                    "arn:aws:iam::*:role/cdk-*",
                    "arn:aws:iam::*:role/SevenK7*",
                    f"arn:aws:iam::*:role/github-actions-*-{github_repo}",
                    "arn:aws:iam::*:policy/cdk-*",
                    "arn:aws:iam::*:policy/SevenK7*",
                ],
            )
        )

        # ── Stack outputs ────────────────────────────────────────────────────
        CfnOutput(
            self,
            "OidcProviderArn",
            value=oidc_provider.open_id_connect_provider_arn,
            description="ARN of the GitHub Actions OIDC identity provider",
            export_name=f"{construct_id}-OidcProviderArn",
        )
        CfnOutput(
            self,
            "DeployRoleArn",
            value=deploy_role.role_arn,
            description=(
                "ARN of the deploy IAM role — add as GitHub secret AWS_DEPLOY_ROLE_ARN"
            ),
            export_name=f"{construct_id}-DeployRoleArn",
        )
        CfnOutput(
            self,
            "ReadonlyRoleArn",
            value=readonly_role.role_arn,
            description=(
                "ARN of the readonly IAM role — add as GitHub secret AWS_READONLY_ROLE_ARN"
            ),
            export_name=f"{construct_id}-ReadonlyRoleArn",
        )

