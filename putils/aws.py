import asyncio
import os

import pulumi
from pulumi_aws import acm, route53, ec2

from .component import component
from .localstack import opts
from .paio import outputish
__all__ = 'get_region', 'Certificate', 'a_aaaa', 'get_public_subnets'


class NoRegionError:
    """
    Raised if we aren't able to detect the current region
    """


def get_region(resource):
    """
    Gets the AWS region for a given resource.
    """
    provider = resource.get_provider('aws::')
    config = pulumi.Config("aws").get('region')
    if provider and provider.region:
        return provider.region
    # These are stolen out of pulumi-aws
    elif config:
        return config
    elif 'AWS_REGION' in os.environ:
        return os.environ['AWS_REGION']
    elif 'AWS_DEFAULT_REGION' in os.environ:
        return os.environ['AWS_DEFAULT_REGION']
    else:
        raise NoRegionError("Unable to determine AWS Region")


@component(outputs=['cert', 'cert_arn'])
def Certificate(self, name, domain, zone, __opts__):
    """
    Gets a TLS certifcate for the given domain, using ACM and DNS validation.

    This will be in us-east-1, suitable for CloudFront
    """
    cert = acm.Certificate(
        f"{name}-certificate",
        domain_name=domain,
        validation_method="DNS",
        **opts(parent=self),
    )

    # TOOD: Multiple DVOs
    dvo = cert.domain_validation_options[0]
    record = route53.Record(
        f"{name}-validation-record",
        name=dvo['resourceRecordName'],
        zone_id=zone.zone_id,
        type=dvo['resourceRecordType'],
        records=[dvo['resourceRecordValue']],
        ttl=10*60,  # 10 minutes
        **opts(parent=self),
    )

    validation = acm.CertificateValidation(
        f"{name}-validation",
        certificate_arn=cert.arn,
        validation_record_fqdns=[record.fqdn],
        **opts(parent=self),
    )

    return {
        'cert': cert,
        'cert_arn': validation.certificate_arn,
    }


def a_aaaa(__name__, *pargs, **kwargs):
    assert 'type' not in kwargs
    a = route53.Record(f"{__name__}-a", *pargs, type='A', **kwargs)
    aaaa = route53.Record(f"{__name__}-aaaa", *pargs, type='AAAA', **kwargs)
    return a, aaaa


@outputish
async def get_public_subnets(vpc=None, opts=None):
    """
    Gets the vpc, public subnets, and if they're IPv6-enabled.

    If no VPC is given, use the default one for the region
    """
    if vpc is None:
        vpc = await ec2.get_vpc(default=True, opts=opts)
    sub_res = await ec2.get_subnet_ids(vpc_id=vpc.id, opts=opts)
    subnets = await asyncio.gather(*(ec2.get_subnet(id=id) for id in sub_res.ids))

    # TODO: Filter for public subnets

    return vpc, subnets, bool(vpc.ipv6_cidr_block)
