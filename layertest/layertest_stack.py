import os
import os.path

from aws_cdk import (
    DockerImage,
    DockerVolume,
    BundlingOptions,
    Duration,
    Stack,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_logs as logs,
    # aws_sqs as sqs,
)
from constructs import Construct


class LayertestStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        permissions_boundary_policy_arn = self.node.try_get_context(
            "PermissionsBoundaryPolicyArn"
        )
        if not permissions_boundary_policy_arn:
            permissions_boundary_policy_name = self.node.try_get_context(
                "PermissionsBoundaryPolicyName"
            )
            if permissions_boundary_policy_name:
                permissions_boundary_policy_arn = self.format_arn(
                    service="iam",
                    region="",
                    account=self.account,
                    resource="policy",
                    resource_name=permissions_boundary_policy_name,
                )

        if permissions_boundary_policy_arn:
            policy = iam.ManagedPolicy.from_managed_policy_arn(
                self, "PermissionsBoundary", permissions_boundary_policy_arn
            )
            iam.PermissionsBoundary.of(self).apply(policy)

        python_runtime = _lambda.Runtime.PYTHON_3_9  # 7

        layer_dir = "layers/skyfield"
        container_dir = "/install"
        opts = "--only-binary :all: --disable-pip-version-check --no-cache-dir"
        # build_image=python_runtime.bundling_image
        # build_image=DockerImage("public.ecr.aws/sam/build-python3.7:1")
        build_image = DockerImage("python:3.9-slim")

        layer_code = _lambda.Code.from_asset(
            layer_dir,
            bundling=BundlingOptions(
                image=build_image,
                volumes=[
                    DockerVolume(
                        container_path=container_dir,
                        host_path=os.path.join(os.getcwd(), layer_dir),
                    )
                ],
                command=f"pip install {opts} -r {container_dir}/requirements.txt -t /asset-output/python".split(),
                network="host",
            ),
        )

        skyfield_layer = _lambda.LayerVersion(
            self,
            "skyfield",
            code=layer_code,
            compatible_runtimes=[python_runtime],
        )

        lambda_code = _lambda.Code.from_inline(
            """
import json
import skyfield
from skyfield.api import Loader

def lambda_handler(event, context):

    print(skyfield.VERSION)

    load = Loader('/tmp')
    planets = load('de421.bsp')
    earth, mars = planets['earth'], planets['mars']

    ts = load.timescale()
    t = ts.now()
    position = earth.at(t).observe(mars)
    ra, dec, distance = position.radec()

    print(ra)
    print(dec)
    print(distance)

    return { 'response' : skyfield.VERSION }

"""
        )

        _lambda.Function(
            self,
            "testfunction",
            code=lambda_code,
            runtime=python_runtime,
            handler="index.lambda_handler",
            timeout=Duration.minutes(1),
            log_retention=logs.RetentionDays.ONE_WEEK,
            layers=[skyfield_layer],
        )
