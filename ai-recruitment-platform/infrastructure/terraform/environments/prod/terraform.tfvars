environment         = "prod"
aws_region          = "ap-south-1"
project_name        = "recruitment"
vpc_cidr            = "10.0.0.0/16"
eks_cluster_version = "1.29"
node_instance_types = ["t3.xlarge", "t3a.xlarge", "m5.xlarge"]
node_min_size       = 3
node_max_size       = 30
node_desired_size   = 5
db_instance_class   = "db.r6g.large"
redis_node_type     = "cache.r6g.large"
domain_name         = "recruitai.io"
# db_password — set via TF_VAR_db_password env variable, never in tfvars
