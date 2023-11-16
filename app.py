#!/usr/bin/env python3
import os
import aws_cdk as cdk

from energy_blog_cdk.network_cdk_stack import NetworkCdkStack
from energy_blog_cdk.directory_cdk_stack import DirectoryCdkStack
from energy_blog_cdk.storage_cdk_stack import StorageCdkStack
from energy_blog_cdk.instance_cdk_stack import InstanceCdkStack

# Setup the environment configuration
deployment_account_id = cdk.Aws.ACCOUNT_ID
deployment_region = cdk.Aws.REGION

deployment_env = cdk.Environment(
    account=deployment_account_id, region=deployment_region)

###########################################################################
# Start here and update the variables below to match your account values. # 
###########################################################################

# 1. You need to create your own key pairs for instance launch. Run the example cli below to create a key pair. 
# aws ec2 create-key-pair --key-name aws-energy-blog-keypair --region ap-southeast-2 --query 'KeyMaterial' --output text > keys.pem
keys = "aws-energy-blog-keypair"

# 2. Update the source IP addresses you will use to access the instances 
source_ips = ["192.168.0.1/32", "192.168.0.2/32"]

#####################################################
# end of account specific values. 
#####################################################

app = cdk.App()
network_stack = NetworkCdkStack(app, "NetworkCdkStack", env=deployment_env)
directory_stack = DirectoryCdkStack(
    app, "DirectoryCdkStack", env=deployment_env, network_cdk_stack=network_stack)
storage_stack = StorageCdkStack(app, "StorageCdkStack", env=deployment_env,
                                network_cdk_stack=network_stack, directory_cdk_stack=directory_stack)
instance_stack = InstanceCdkStack(
    app, "InstanceCdkStack", env=deployment_env, network_cdk_stack=network_stack, directory_cdk_stack=directory_stack, keys=keys, sg_source_ips=source_ips )
app.synth()