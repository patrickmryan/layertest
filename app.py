import os
import aws_cdk as cdk

from layertest.layertest_stack import LayertestStack

app = cdk.App()
deployment_name = app.node.try_get_context("DeploymentName")
suffix = f"-{deployment_name}" if deployment_name else ""

LayertestStack(app, "LayertestStack" + suffix)

app.synth()
