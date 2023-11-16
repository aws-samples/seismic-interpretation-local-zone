from aws_cdk import (
    Stack,
    Tags,
    CfnTag
)
from aws_cdk import aws_directoryservice as ad
import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_iam as iam
import aws_cdk.aws_ssm as ssm
from constructs import Construct

# Params
nice_dcv_ami = ec2.MachineImage.generic_windows(
    {"ap-southeast-2": "ami-0c647d0850806d035"})


class InstanceCdkStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, network_cdk_stack, directory_cdk_stack, keys, env, sg_source_ips, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # This stack is builds instances for the energy blog solution.

        # Create SSM Document to join domain and install tools
        cfn_document = ssm.CfnDocument(self, "join-domain-install-software-doc",
                                       content={
                                           "schemaVersion": "2.2",
                                           "description": "aws:runPowerShellScript",
                                           "parameters": {
                                               "directoryId": {
                                                   "description": "(Required) The ID of the directory.",
                                                   "type": "String"
                                               },
                                               "directoryName": {
                                                   "description": "(Required) The name of the domain.",
                                                   "type": "String"
                                               },
                                               "dnsIpAddresses": {
                                                   "description": "(Required) The IP addresses of the DNS servers for your directory.",
                                                   "type": "StringList"
                                               }
                                           },
                                           "mainSteps": [
                                               {
                                                   "action": "aws:domainJoin",
                                                   "name": "domainJoin",
                                                   "inputs": {
                                                       "directoryId": "{{ directoryId }}",
                                                       "directoryName": "{{ directoryName }}",
                                                       "dnsIpAddresses": "{{ dnsIpAddresses }}"
                                                   }
                                               },
                                               {
                                                   "action": "aws:runPowerShellScript",
                                                   "name": "InstallRSATTools",
                                                   "inputs": {
                                                       "timeoutSeconds": "180",
                                                       "runCommand": [
                                                           "Install-WindowsFeature RSAT-ADDS"
                                                       ],
                                                       "finallyStep": True
                                                   }
                                               }
                                           ]
                                       },
                                       name="join-domain-install-software",
                                       document_type="Command",
                                       tags=[CfnTag(
                                           key="Name",
                                           value="join-domain-install-software"
                                       )]
                                       )

        # Create a security group
        sg_name = "nice-dcv-perth-instance-sg"
        self.security_group = ec2.SecurityGroup(self, "nice-dcv-perth-instance-sg",
                                                vpc=network_cdk_stack.workload_vpc,
                                                description=sg_name,
                                                allow_all_outbound=True,
                                                security_group_name=sg_name
                                                )
        Tags.of(self.security_group).add("Name", sg_name)

        # Add an inbound rule to allow traffic from a specific IP address
        for ip in sg_source_ips:
            self.security_group.add_ingress_rule(
                ec2.Peer.ipv4(ip),
                ec2.Port.tcp(3389),
                "Allow traffic from a specific IP address"
            )
            self.security_group.add_ingress_rule(
                ec2.Peer.ipv4(ip),
                ec2.Port.tcp(8443),
                "Allow traffic from a specific IP address"
            )
        
        self.security_group.add_ingress_rule(
                ec2.Peer.ipv4("10.0.50.0/24"),
                ec2.Port.tcp(445),
                "Allow traffic from a Perth Subnet"
            )

        # Create IAM role
        role = iam.Role(self, 'perth-ec2-role',
                        assumed_by=iam.ServicePrincipal('ec2.amazonaws.com'),
                        )
        role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name(
            'AmazonSSMManagedInstanceCore'))
        role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name(
            'AmazonSSMDirectoryServiceAccess'))

        # Attach policy to the role
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:GetObject"],
                resources=["arn:aws:s3:::dcv-license." + env.region + "/*"],
            )
        )

        # Grab the Perth subnet as an ISubnet object
        perth_subnet = ec2.Subnet.from_subnet_attributes(
            self, "sn-lookup", subnet_id=network_cdk_stack.sn.attr_subnet_id, availability_zone=network_cdk_stack.sn.attr_availability_zone)

        # Create the user instance
        friendly_name = "nice-dcv-perth-instance"
        perth_instance = ec2.Instance(self, "perth-instance", instance_type=ec2.InstanceType.of(
            ec2.InstanceClass.G4DN, ec2.InstanceSize.XLARGE2),
            machine_image=nice_dcv_ami,
            vpc=network_cdk_stack.workload_vpc,
            vpc_subnets=ec2.SubnetSelection(
            subnets=[perth_subnet]),
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/sda2",
                    volume=ec2.BlockDeviceVolume.ebs(100, 
                        delete_on_termination=True,
                        encrypted=True
                    ),
                )
            ],
            instance_name=friendly_name,
            role=role,
            key_name=keys,
            detailed_monitoring=True,
            security_group=self.security_group)
        Tags.of(perth_instance).add("purpose", "energy-blog")
        # Enable termination protection - https://docs.aws.amazon.com/cdk/v2/guide/cfn_layer.html#cfn_layer_resource
        cfn_perth_instance = perth_instance.node.default_child
        cfn_perth_instance.disable_api_termination=True

        # Create the cache - core instance - sydney
        core_friendly_name = "cache-instance-core"
        self.cache_core_security_group = ec2.SecurityGroup(self, core_friendly_name+"-sg",
                                                           vpc=network_cdk_stack.workload_vpc,
                                                           description=core_friendly_name+" security group",
                                                           allow_all_outbound=True,
                                                           security_group_name=core_friendly_name+"-sg"
                                                           )
        Tags.of(self.cache_core_security_group).add(
            "Name", core_friendly_name+"-sg")

        self.cache_core_security_group.add_ingress_rule(
            ec2.Peer.security_group_id(
                self.security_group.security_group_id),
            ec2.Port.all_traffic(),
            "Allow traffic from nice-dcv-perth-instance-sg"
        )

        cache_instance_core = ec2.Instance(self, "cache-instance-core", instance_type=ec2.InstanceType.of(
            ec2.InstanceClass.T3, ec2.InstanceSize.XLARGE),
            machine_image=ec2.MachineImage.latest_windows(
                ec2.WindowsVersion.WINDOWS_SERVER_2022_ENGLISH_FULL_BASE),
            vpc=network_cdk_stack.workload_vpc,
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/sda1",
                    mapping_enabled=True,
                    volume=ec2.BlockDeviceVolume.ebs(100, 
                        delete_on_termination=True,
                        encrypted=True
                    ),
                )
            ],
            instance_name=core_friendly_name,
            role=role,
            key_name=keys,
            detailed_monitoring=True,
            security_group=self.cache_core_security_group)
        Tags.of(cache_instance_core).add("purpose", "energy-blog")
        # Enable termination protection - https://docs.aws.amazon.com/cdk/v2/guide/cfn_layer.html#cfn_layer_resource
        cfn_cache_instance_core = cache_instance_core.node.default_child
        cfn_cache_instance_core.disable_api_termination=True
        

        # Create the cache - edge instance - perth
        edge_friendly_name = "cache-instance-edge"
        cache_instance_edge = ec2.Instance(self, "cache-instance-edge", instance_type=ec2.InstanceType.of(
            ec2.InstanceClass.R5, ec2.InstanceSize.XLARGE2),
            machine_image=ec2.MachineImage.latest_windows(
                ec2.WindowsVersion.WINDOWS_SERVER_2022_ENGLISH_FULL_BASE),
            vpc=network_cdk_stack.workload_vpc,
            vpc_subnets=ec2.SubnetSelection(
            subnets=[perth_subnet]),
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/sda2",
                    volume=ec2.BlockDeviceVolume.ebs(1000,
                        delete_on_termination=True,
                        encrypted=True)
                )
        ],
            instance_name=edge_friendly_name,
            role=role,
            key_name=keys,
            detailed_monitoring=True,
            security_group=self.security_group)
        Tags.of(cache_instance_edge).add("purpose", "energy-blog")
        # Enable termination protection - https://docs.aws.amazon.com/cdk/v2/guide/cfn_layer.html#cfn_layer_resource
        cfn_cache_instance_edge = cache_instance_edge.node.default_child
        cfn_cache_instance_edge.disable_api_termination=True

        # Attach SSM Doc to instances
        instance_domain_join = ssm.CfnAssociation(self, "domain-join",
                                                  name=cfn_document.name,
                                                  parameters={
                                                      "directoryId": [directory_cdk_stack.managed_ad.attr_alias],
                                                      "directoryName": [directory_cdk_stack.managed_ad.name],
                                                      "dnsIpAddresses": [directory_cdk_stack.managed_ad.attr_dns_ip_addresses[0]]
                                                  },
                                                  targets=[ssm.CfnAssociation.TargetProperty(
                                                      key="tag:purpose",
                                                      values=["energy-blog"]
                                                  )],
                                                  wait_for_success_timeout_seconds=300
                                                  )
        instance_domain_join.add_dependency(cfn_document)