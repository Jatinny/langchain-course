output "eks_cluster_endpoint" {
  description = "EKS cluster API endpoint"
  value       = module.compute.cluster_endpoint
  sensitive   = true
}

output "eks_cluster_name" {
  description = "EKS cluster name"
  value       = module.compute.cluster_name
}

output "rds_endpoint" {
  description = "PostgreSQL RDS endpoint"
  value       = module.database.rds_endpoint
  sensitive   = true
}

output "redis_endpoint" {
  description = "ElastiCache Redis endpoint"
  value       = module.database.redis_endpoint
  sensitive   = true
}

output "kafka_bootstrap_servers" {
  description = "MSK Kafka bootstrap servers"
  value       = length(aws_msk_cluster.kafka) > 0 ? aws_msk_cluster.kafka[0].bootstrap_brokers : "localhost:9092"
  sensitive   = true
}

output "ecr_registry_url" {
  description = "ECR registry base URL"
  value       = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com"
}

output "s3_resumes_bucket" {
  description = "S3 bucket for resume storage"
  value       = aws_s3_bucket.resumes.bucket
}

output "vpc_id" {
  description = "VPC ID"
  value       = module.networking.vpc_id
}

data "aws_caller_identity" "current" {}
