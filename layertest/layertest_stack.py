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
    # aws_sqs as sqs,
)
from constructs import Construct


class LayertestStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        permissions_boundary_policy_arn = self.node.try_get_context(
            "PermissionsBoundaryPolicyArn"
        )
        if permissions_boundary_policy_arn:
            print(f"boundary policy is {permissions_boundary_policy_arn}")
            policy = (
                iam.ManagedPolicy.from_managed_policy_arn(  #   from_managed_policy_name
                    self, "PermissionsBoundary", permissions_boundary_policy_arn
                )
            )
            iam.PermissionsBoundary.of(self).apply(policy)

        layer_dir = "layers/skyfield"
        container_dir = "/install"
        layer_code = _lambda.Code.from_asset(
            layer_dir,
            bundling=BundlingOptions(
                image=DockerImage("public.ecr.aws/sam/build-python3.7:1"),
                volumes=[
                    DockerVolume(
                        container_path=container_dir,
                        host_path=os.path.join(os.getcwd(), layer_dir),
                    )
                ],
                # command=[
                #     "/bin/sh",
                #     "-c",
                #     f"pip install -r {container_dir}/requirements.txt -t /asset-output/python",
                # ],
                command=f"pip install -r {container_dir}/requirements.txt -t /asset-output/python".split(),
            ),
        )

        python_runtime = _lambda.Runtime.PYTHON_3_7
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
from skyfield.api import load

def lambda_handler(event, context):

    print(skyfield.VERSION)

    planets = load('de421.bsp')
    earth, mars = planets['earth'], planets['mars']
    
    ts = load.timescale()
    t = ts.now()
    position = earth.at(t).observe(mars)
    ra, dec, distance = position.radec()
    
    print(ra)
    print(dec)
    print(distance)

"""
        )

        _lambda.Function(
            self,
            "testfunction",
            code=lambda_code,
            runtime=python_runtime,
            handler="index.lambda_handler",
            timeout=Duration.minutes(1),
            layers=[skyfield_layer],
        )
