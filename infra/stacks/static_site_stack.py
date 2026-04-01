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

    CDK context keys
    ----------------
    domain_name    : str  – e.g. ``7k7.synthesis.run`` (required)
    hosted_zone_id : str  – Route 53 hosted-zone ID (optional); when provided
                           an ACM certificate and ALIAS record are created
                           automatically.  The stack must be deployed in
                           ``us-east-1`` so that the certificate is co-located
                           with CloudFront.
    certificate_arn : str – ARN of a pre-validated ACM certificate in
                            ``us-east-1`` (optional, used when the domain is
                            managed by external DNS).  Takes effect only when
                            ``hosted_zone_id`` is not provided.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs: object) -> None:
        super().__init__(scope, construct_id, **kwargs)

        domain_name: str = self.node.try_get_context("domain_name") or "7k7.synthesis.run"
        hosted_zone_id: str | None = self.node.try_get_context("hosted_zone_id")
        certificate_arn: str | None = self.node.try_get_context("certificate_arn")

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
        # Two supported paths:
        #   1. hosted_zone_id — Route 53 managed: CDK creates & auto-validates the cert.
        #   2. certificate_arn — External DNS: import a pre-validated ACM cert by ARN.
        #      Create the cert manually (console / CLI), complete DNS validation, then
        #      pass the ARN via: cdk deploy -c certificate_arn=<arn>
        certificate: acm.ICertificate | None = None
        hosted_zone: route53.IHostedZone | None = None
        if hosted_zone_id:
            hosted_zone = route53.HostedZone.from_hosted_zone_attributes(
                self,
                "HostedZone",
                hosted_zone_id=hosted_zone_id,
                zone_name=domain_name,
            )
            certificate = acm.Certificate(
                self,
                "SiteCertificate",
                domain_name=domain_name,
                validation=acm.CertificateValidation.from_dns(hosted_zone),
            )
        elif certificate_arn:
            certificate = acm.Certificate.from_certificate_arn(
                self,
                "SiteCertificate",
                certificate_arn,
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
            domain_names=[domain_name] if certificate else None,
            certificate=certificate,
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
            http_version=cloudfront.HttpVersion.HTTP2_AND_3,
        )

        # ── Route 53 alias record (optional) ────────────────────────────────
        if hosted_zone and certificate:
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
        if certificate:
            CfnOutput(
                self,
                "CertificateArn",
                value=certificate.certificate_arn,
                description="ACM certificate ARN attached to the CloudFront distribution",
                export_name=f"{construct_id}-CertificateArn",
            )
