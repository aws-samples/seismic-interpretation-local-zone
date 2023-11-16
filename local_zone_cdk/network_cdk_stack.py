from aws_cdk import (
    Stack,
    CfnTag
)
import aws_cdk.aws_secretsmanager as secretsManager
import aws_cdk.aws_ec2 as ec2
from aws_cdk import aws_logs as logs
from constructs import Construct

class NetworkCdkStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # # This stack is for shared and prerequisite resources

        # ManagedAD secret to provision directory services
        self.secret = secretsManager.Secret(self, 'managed-ad-secret', description="Managed AD password"
                                            )

        # Create a VPC
        self.workload_vpc = ec2.Vpc(self, "workload-vpc", vpc_name="energy-blog-vpc",
                                    max_azs=2,
                                    subnet_configuration=[
                                        ec2.SubnetConfiguration(
                                            name="Public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24
                                        ),
                                        ec2.SubnetConfiguration(
                                            name="Private", subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS, cidr_mask=24
                                        )
                                    ])
        
        # Create a Flow Log Group (for storing log data)
        log_group = logs.LogGroup(
            self,
            "vpc-flow-logs",
            retention=logs.RetentionDays.ONE_MONTH,  # Adjust retention period as needed
        )

        # Create a Flow Log and associate it with the VPC
        flow_log = ec2.FlowLog(
            self,
            "vpc-flow-log",
            resource_type=ec2.FlowLogResourceType.from_vpc(self.workload_vpc),
            destination=ec2.FlowLogDestination.to_cloud_watch_logs(log_group),
            traffic_type=ec2.FlowLogTrafficType.ALL,
        )

        # Create Perth subnet in Workoad vpc
        self.sn = ec2.CfnSubnet(self, "perth-lz-subnet", vpc_id=self.workload_vpc.vpc_id,
                                availability_zone="ap-southeast-2-per-1a", cidr_block="10.0.50.0/24", map_public_ip_on_launch=True,                                                    
                                tags=[CfnTag(
                                    key="Name",
                                    value="perth-lz-subnet"
                                )])

        # Create Perth route table in Workoad vpc
        self.perth_route_table = ec2.CfnRouteTable(self, "perth-lz-route-table",
                                                   vpc_id=self.workload_vpc.vpc_id,
                                                   tags=[CfnTag(
                                                       key="Name",
                                                       value="perth-lz-route-table"
                                                   )]
                                                   )
        self.perth_route_table.add_dependency(self.sn)

        # Add route to internet for Perth Subnet
        cfn_route = ec2.CfnRoute(self, "perth-internet-route",
                                 route_table_id=self.perth_route_table.attr_route_table_id,
                                 destination_cidr_block="0.0.0.0/0",
                                 gateway_id=self.workload_vpc.internet_gateway_id,
                                 )

        # Associate the route table with the subnet
        cfn_subnet_route_table_association = ec2.CfnSubnetRouteTableAssociation(self, "perth-route-table-association",
                                                                                route_table_id=self.perth_route_table.attr_route_table_id,
                                                                                subnet_id=self.sn.attr_subnet_id
                                                                                )
        cfn_subnet_route_table_association.add_dependency(
            self.perth_route_table)
        

        # Iterate the private subnets
        selection = self.workload_vpc.select_subnets(
            subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
        )

        # Store the private route table id's for later
        self.private_route_tables = []
        self.private_route_tables.append(self.perth_route_table.attr_route_table_id)
        
        for subnet in selection.subnets:
            self.private_route_tables.append(subnet.route_table.route_table_id)