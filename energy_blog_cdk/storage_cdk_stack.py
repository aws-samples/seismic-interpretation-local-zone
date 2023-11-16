from aws_cdk import (
    Stack,
    CfnTag,
    Tags
)

import aws_cdk.aws_ec2 as ec2
from aws_cdk import aws_fsx as fsx

from constructs import Construct

class StorageCdkStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, network_cdk_stack, directory_cdk_stack, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # # This stack is for storage resources
        private_subnet_ids = [
            subnet.subnet_id for subnet in network_cdk_stack.workload_vpc.private_subnets]

        # Create a security group
        sg_name = "netapp-fsx-sg"
        self.fsx_security_group = ec2.SecurityGroup(self, "netapp-fsx-sg",
                                                    vpc=network_cdk_stack.workload_vpc,
                                                    description=sg_name,
                                                    allow_all_outbound=True,
                                                    security_group_name=sg_name
                                                    )
        Tags.of(self.fsx_security_group).add("Name", sg_name)

        self.fsx_security_group.add_ingress_rule(
            ec2.Peer.ipv4('10.0.0.0/16'),
            ec2.Port.tcp(445),
            "Allow SMB traffic from VPC"
        )

        # Create the FSX file system
        cfn_file_system = fsx.CfnFileSystem(self, "energy-blog-ontap",
                                            file_system_type="ONTAP",
                                            subnet_ids=private_subnet_ids,
                                            ontap_configuration=fsx.CfnFileSystem.OntapConfigurationProperty(
                                                deployment_type="MULTI_AZ_1",
                                                automatic_backup_retention_days=0,
                                                daily_automatic_backup_start_time="06:00",
                                                fsx_admin_password=directory_cdk_stack.unwrap_pw,
                                                preferred_subnet_id=private_subnet_ids[0],
                                                route_table_ids=network_cdk_stack.private_route_tables,
                                                endpoint_ip_address_range="10.0.255.0/24",
                                                throughput_capacity=512,
                                            ),
                                            security_group_ids=[
                                                self.fsx_security_group.security_group_id],
                                            storage_capacity=1024,
                                            storage_type="SSD",
                                            tags=[CfnTag(
                                                key="Name",
                                                value="energy-blog-fsx-cluster"
                                            )],
                                            )

        # Create the storage virtual machine and join to the domain
        cfn_storage_virtual_machine = fsx.CfnStorageVirtualMachine(self, "energy-blog-svm",
                                                                   file_system_id=cfn_file_system.ref,
                                                                   name="energy-blog-svm",
                                                                   active_directory_configuration=fsx.CfnStorageVirtualMachine.ActiveDirectoryConfigurationProperty(
                                                                       net_bios_name="blogdatasvm",
                                                                       self_managed_active_directory_configuration=fsx.CfnStorageVirtualMachine.SelfManagedActiveDirectoryConfigurationProperty(
                                                                           dns_ips=directory_cdk_stack.managed_ad.attr_dns_ip_addresses,
                                                                           domain_name=directory_cdk_stack.managed_ad.name,
                                                                           file_system_administrators_group="AWS Delegated Administrators",
                                                                           organizational_unit_distinguished_name="OU=Computers,OU=energyblog,DC=energyblog,DC=example,DC=com",
                                                                           password=directory_cdk_stack.unwrap_pw,
                                                                           user_name="Admin"
                                                                       )
                                                                   ),
                                                                   root_volume_security_style="NTFS",
                                                                   tags=[CfnTag(
                                                                       key="Name",
                                                                       value="energy-blog-data-svm"
                                                                   )]
                                                                   )
        cfn_storage_virtual_machine.add_dependency(cfn_file_system)

        cfn_volume = fsx.CfnVolume(self, "energy-blog-ontap-volume",
                                   name="energy_blog_ontap_volume",
                                   ontap_configuration=fsx.CfnVolume.OntapConfigurationProperty(
                                       size_in_megabytes="100000",
                                       storage_virtual_machine_id=cfn_storage_virtual_machine.attr_storage_virtual_machine_id,
                                       junction_path="/vol1",
                                       ontap_volume_type="RW",
                                       security_style="NTFS",
                                       snapshot_policy="default",
                                       storage_efficiency_enabled="true",
                                       tiering_policy=fsx.CfnVolume.TieringPolicyProperty(
                                           cooling_period=14,
                                           name="AUTO"
                                       )
                                   ),
                                   tags=[CfnTag(
                                       key="Name",
                                       value="energy-blog-primary-volume"
                                   )],
                                   volume_type="ONTAP"
                                   )
        cfn_volume.add_dependency(cfn_storage_virtual_machine)
