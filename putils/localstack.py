"""
Utilities to deal with localstack/aws switching
"""

import os

import pulumi
import pulumi_aws

__all__ = 'get_provider_for_region', 'opts',

PROVIDER = None

if os.environ.get('STAGE') == 'local':
    PROVIDER = pulumi_aws.Provider(
        "localstack",
        skip_credentials_validation=True,
        skip_metadata_api_check=True,
        s3_force_path_style=True,
        access_key="mockAccessKey",
        secret_key="mockSecretKey",
        region='us-east-1',
        endpoints=[{
            'apigateway': "http://localhost:4567",
            'cloudformation': "http://localhost:4581",
            'cloudwatch': "http://localhost:4582",
            'cloudwatchlogs': "http://localhost:4586",
            'dynamodb': "http://localhost:4569",
            # "DynamoDBStreams": "http://localhost:4570",
            # "Elasticsearch": "http://localhost:4571",
            'es': "http://localhost:4578",
            'firehose': "http://localhost:4573",
            'iam': "http://localhost:4593",
            'kinesis': "http://localhost:4568",
            'kms': "http://localhost:4584",
            'lambda': "http://localhost:4574",
            'redshift': "http://localhost:4577",
            'route53': "http://localhost:4580",
            's3': "http://localhost:4572",
            'ses': "http://localhost:4579",
            # "StepFunctions": "http://localhost:4585",
            'sns': "http://localhost:4575",
            'sqs': "http://localhost:4576",
            'ssm': "http://localhost:4583",
            'sts': "http://localhost:4592",
        }],
    )

_provider_cache = {}


def get_provider_for_region(region):
    if PROVIDER is not None:
        # Using localstack
        return PROVIDER

    assert isinstance(region, str)
    if region not in _provider_cache:
        _provider_cache[region] = pulumi_aws.Provider(
            region,
            # profile=pulumi_aws.config.profile, # FIXME
            region=region,
        )

    return _provider_cache[region]


def opts(*, region=None, **kwargs):
    """
    Defines an __opts__ for resources, including any localstack config.

    localstack config is only applied if this is a top-level component (does not
    have a parent).

    Adds a parameter `region` that will produce a Provider for the given aws region.

    Usage:
    >>> Resource(..., **opts(...))
    """
    if PROVIDER is not None:
        # Using localstack
        if 'parent' not in kwargs:
            # Unless a parent is set, in which case lets use inheritance
            kwargs.setdefault('provider', PROVIDER)
    elif region is not None:
        assert 'provider' not in kwargs
        # Specified a specific region (and not using localstatck)
        kwargs['provider'] = get_provider_for_region(region)
    return {
        '__opts__': pulumi.ResourceOptions(**kwargs)
    }
