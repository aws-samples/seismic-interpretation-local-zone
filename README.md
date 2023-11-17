
# AWS Perth Local Zone Latency Test Environment

This pattern will accelerate the deployment of a test environment to perform latency tests to the perth local zone from your own network. You can review the blog article that discusses this in depth here - [Ultralow latency seismic interpretation on AWS Local Zones](https://aws.amazon.com/blogs/industries/ultralow-latency-seismic-interpretation-on-aws-local-zones/)

## Requirements

* [Create an AWS account](https://portal.aws.amazon.com/gp/aws/developer/registration/index.html) if you do not already have one and log in. The IAM user that you use must have sufficient permissions to make necessary AWS service calls and manage AWS resources.
* [Bootstrap](https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping.html#bootstrapping-howto) your account to prepare for CDK deployments
* [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) installed and configured
* [Git Installed](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
* [AWS CDK Toolkit](https://docs.aws.amazon.com/cdk/latest/guide/cli.html) installed and configured
* [Python 3.9+](https://www.python.org/downloads/) installed

## Prerequisite Steps

1. Opt into the AWS perth local zone - [Instructions here](https://docs.aws.amazon.com/local-zones/latest/ug/getting-started.html#getting-started-find-local-zone) - You DO NOT need to create the subnet (per the instructions.) The CDK application will do this for you. 
    ```
    aws ec2 modify-availability-zone-group \
    --region ap-southeast-2 \
    --group-name ap-southeast-2-per-1a \
    --opt-in-status opted-in
    ```
2. Create your key pair for your EC2 Instances
    ```
    aws ec2 create-key-pair --key-name aws-energy-blog-keypair --region ap-southeast-2 --query 'KeyMaterial' --output text > keys.pem
    ```
3. Update the ```keys``` variable with the key pair name in ```app.py``` on line 25.
    ```
    keys = "aws-energy-blog-keypair"
    ```
4. Identify your source ip which will be used to access the environment 
    ```
    curl ipinfo.io
    ```
5. Update the ```source_ips``` variable in ```app.py``` on line 28 with the IP addresses you will use to access the environment. These are used to buld rules in the security group. 
    ```
    source_ips = ["192.168.0.1/32", "192.168.0.2/32"]
    ```

## Deployment Instructions

1. Create a new directory, navigate to that directory in a terminal and clone the GitHub repository:
    ```
    git clone https://github.com/aws-samples/seismic-interpretation-local-zone.git
    ```
2. Change directory to the pattern directory:
    ```
    cd seismic-interpretation-local-zone
    ```
3. Create a virtual environment for Python
    ```
    python3 -m venv .venv
    ```
4. Activate the virtual environment
    ```
    source .venv/bin/activate
    ```
    For a Windows platform, activate the virtualenv like this:
    ```
    .venv\Scripts\activate.bat
    ```
5. Install the Python required dependencies:
    ```
    pip3 install -r requirements.txt
    ```
6. From the command line, use AWS CDK to deploy the AWS resources for the serverless application as specified in the app.py file:
    ```
    cdk deploy --all
    ```
7. Note the outputs from the CDK deployment process. These contain important information which is used for testing.
8. The CDK application creates a secret in AWS Secrets Manager that is used to configure AWS Managed Microsoft AD. This secret is also used to join the services to the domain during the build process. You will need to [retrieve the secret](https://docs.aws.amazon.com/secretsmanager/latest/userguide/retrieving-secrets.html#retrieving-secrets-console) to perform an initial login to the environment using the [Admin account](https://docs.aws.amazon.com/directoryservice/latest/admin-guide/ms_ad_getting_started_admin_account.html) (prior to creating your own account.)
9.  All instances are domain joined and have the Active Directory Administration Tools installed. [Login](https://docs.aws.amazon.com/AWSEC2/latest/WindowsGuide/connecting_to_windows_instance.html#connect-rdp) to the ```nice-dcv-perth-instance``` using the [Admin account](https://docs.aws.amazon.com/directoryservice/latest/admin-guide/ms_ad_getting_started_admin_account.html), and follow the guidance to [create a user](https://docs.aws.amazon.com/directoryservice/latest/admin-guide/ms_ad_manage_users_groups_create_user.html) in AWS AWS Managed Microsoft AD. 
10. Add the user to the [required groups](https://docs.aws.amazon.com/directoryservice/latest/admin-guide/ms_ad_getting_started_what_gets_created.html) to manage domain permissions. We **strongly recommend** creating your own service account to manage the directory, and generic user accounts required to test the deployed solution. 
11. Once you have confirmed you can manage the directory, [reset the password](https://docs.aws.amazon.com/directoryservice/latest/admin-guide/ms_ad_manage_users_groups_reset_password.html) for the [Admin account](https://docs.aws.amazon.com/directoryservice/latest/admin-guide/ms_ad_getting_started_admin_account.html) using a long password (at most 64 random characters) and then disable the account
12. [Delete the AWS Secrets Manager secret](https://docs.aws.amazon.com/secretsmanager/latest/userguide/manage_delete-secret.html) that is configured at build time. This is prefixed with ```managedadsecret```
13. You are now ready to commence testing. 

## Useful commands

 * `cdk ls`          list all stacks in the app
 * `cdk synth`       emits the synthesized CloudFormation template
 * `cdk deploy`      deploy this stack to your default AWS account/region
 * `cdk diff`        compare deployed stack with current state
 * `cdk docs`        open CDK documentation

Enjoy!

## Cleanup

1. Delete the stack
    ```
    cdk destroy --all
    ```

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.