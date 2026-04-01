"""Main CDK stack for the 7K7 static site hosted on S3 + CloudFront."""
from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_certificatemanager as acm,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_s3 as s3,
)
from constructs import Construct


class StaticSiteStack(Stack):
    """Provisions S3 + CloudFront (+ optional ACM cert / Route 53) for the
    7K7 static site.

    Configuration keys
    ------------------
    domain_name    : str  – e.g. ``7k7.synthesis.run`` (required)
    hosted_zone_id : str  – Route 53 hosted-zone ID (optional); when provided
                           an ACM certificate and ALIAS record are created
                           automatically.  The stack must be deployed in
                           ``us-east-1`` so that the certificate is co-located
                           with CloudFront.
    hosted_zone_name : str – Hosted zone DNS name (optional, defaults to
                             ``domain_name``). Use this when the zone is a
                             parent/apex (e.g. ``synthesis.run``) and the site
                             domain is a subdomain (e.g. ``7k7.synthesis.run``).
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs: object) -> None:
        super().__init__(scope, construct_id, **kwargs)

        domain_name: str = self.node.try_get_context("domain_name") or "7k7.synthesis.run"
        hosted_zone_id: str | None = self.node.try_get_context("hosted_zone_id")
        hosted_zone_name: str = self.node.try_get_context("hosted_zone_name") or domain_name

        if not hosted_zone_id:
            raise ValueError(
                "Missing required config key 'hosted_zone_id'. Set it in infra/config.toml [cdk]."
            )

        # ── S3 bucket ────────────────────────────────────────────────────────
        bucket = s3.Bucket(
            self,
            "SiteBucket",
            bucket_name=f"{domain_name}-site",
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
            website_index_document="index.html",
            website_error_document="index.html",
        )

        # ── ACM certificate (must be in us-east-1 for CloudFront) ───────────
        # Supported path:
        #   hosted_zone_id — Route 53 managed: CDK creates & auto-validates the cert.
        hosted_zone = route53.HostedZone.from_hosted_zone_attributes(
            self,
            "HostedZone",
            hosted_zone_id=hosted_zone_id,
            zone_name=hosted_zone_name,
        )
        # Use a new logical ID so deployments can recover from a previously FAILED cert.
        certificate = acm.Certificate(
            self,
            "SiteCertV2",
            domain_name=domain_name,
            validation=acm.CertificateValidation.from_dns(hosted_zone),
        )

        # ── S3 origin with Origin Access Control (OAC) ──────────────────────
        # S3BucketOrigin.with_origin_access_control() creates the OAC and
        # adds the required bucket policy automatically.
        s3_origin = origins.S3BucketOrigin.with_origin_access_control(bucket)

        # ── Cache policies ───────────────────────────────────────────────────
        static_assets_cache_policy = cloudfront.CachePolicy(
            self,
            "StaticAssetsCachePolicy",
            cache_policy_name=f"{construct_id}-static-assets",
            default_ttl=Duration.days(365),
            max_ttl=Duration.days(365),
            min_ttl=Duration.seconds(0),
            enable_accept_encoding_brotli=True,
            enable_accept_encoding_gzip=True,
        )

        # ── CloudFront distribution ──────────────────────────────────────────
        distribution = cloudfront.Distribution(
            self,
            "Distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=s3_origin,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                origin_request_policy=cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN,
            ),
            additional_behaviors={
                "css/*": cloudfront.BehaviorOptions(
                    origin=s3_origin,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    cache_policy=static_assets_cache_policy,
                ),
                "js/*": cloudfront.BehaviorOptions(
                    origin=s3_origin,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    cache_policy=static_assets_cache_policy,
                ),
                "assets/*": cloudfront.BehaviorOptions(
                    origin=s3_origin,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    cache_policy=static_assets_cache_policy,
                ),
            },
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.minutes(5),
                ),
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.minutes(5),
                ),
            ],
            domain_names=[domain_name],
            certificate=certificate,
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
            http_version=cloudfront.HttpVersion.HTTP2_AND_3,
        )

        # ── Route 53 alias record (optional) ────────────────────────────────
        route53.ARecord(
            self,
            "AliasRecord",
            zone=hosted_zone,
            record_name=domain_name,
            target=route53.RecordTarget.from_alias(
                targets.CloudFrontTarget(distribution)
            ),
        )

        # ── Stack outputs ────────────────────────────────────────────────────
        CfnOutput(
            self,
            "BucketName",
            value=bucket.bucket_name,
            description="S3 bucket name for the static site",
            export_name=f"{construct_id}-BucketName",
        )
        CfnOutput(
            self,
            "DistributionId",
            value=distribution.distribution_id,
            description="CloudFront distribution ID",
            export_name=f"{construct_id}-DistributionId",
        )
        CfnOutput(
            self,
            "DistributionDomainName",
            value=distribution.distribution_domain_name,
            description="CloudFront domain name (use for manual DNS if Route 53 is not managed here)",
            export_name=f"{construct_id}-DistributionDomainName",
        )
        CfnOutput(
            self,
            "CertificateArn",
            value=certificate.certificate_arn,
            description="ACM certificate ARN attached to the CloudFront distribution",
            export_name=f"{construct_id}-CertificateArn",
        )
