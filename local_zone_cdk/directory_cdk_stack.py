from aws_cdk import (
    Stack,
    CfnTag,
    SecretValue
)
from aws_cdk import aws_directoryservice as ad
import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_secretsmanager as sm
import aws_cdk.aws_iam as iam
from constructs import Construct

# Params
inst_type = ec2.InstanceType.of(
    ec2.InstanceClass.G4DN, ec2.InstanceSize.XLARGE2)
nice_dcv_ami = ec2.MachineImage.generic_windows(
    {"ap-southeast-2": "ami-0c647d0850806d035"})

class DirectoryCdkStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, network_cdk_stack, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # # This stack is for resources used to build the energy blog solution.

        # Import the secret for Managed AD.
        secret = sm.Secret.from_secret_attributes(self, "import-secret",
                                                  secret_complete_arn=network_cdk_stack.secret.secret_arn,
                                                  )
        pw = SecretValue.secrets_manager(secret_id=secret.secret_arn)
        self.unwrap_pw = pw.unsafe_unwrap()

        # # Managed AD
        private_subnet_ids = [
            subnet.subnet_id for subnet in network_cdk_stack.workload_vpc.private_subnets]

        self.managed_ad = ad.CfnMicrosoftAD(self,
                                            name="energyblog.example.com",
                                            id="energy-blog-directory",
                                            password=self.unwrap_pw,
                                            edition="Standard",
                                            vpc_settings=ad.CfnMicrosoftAD.VpcSettingsProperty(
                                                subnet_ids=private_subnet_ids,
                                                vpc_id=network_cdk_stack.workload_vpc.vpc_id
                                            ),
                                            short_name="energyblog"
                                            )

        # Create DHCP options set to use Managed AD for internal DNS resolution
        dhcp_options = ec2.CfnDHCPOptions(self, "vpc-dhcp-options", domain_name=self.managed_ad.name, domain_name_servers=self.managed_ad.attr_dns_ip_addresses, tags=[CfnTag(
            key="Name",
            value="energy-blog-vpc-dhcp-opt"
        )])
        dhcp_options.add_dependency(self.managed_ad)

        associate_dhcp_options = ec2.CfnVPCDHCPOptionsAssociation(self, "associate-dhcp-options", dhcp_options_id=dhcp_options.attr_dhcp_options_id,
                                                                  vpc_id=network_cdk_stack.workload_vpc.vpc_id)
