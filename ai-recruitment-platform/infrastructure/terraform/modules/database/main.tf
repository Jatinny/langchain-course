variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "db_instance_class" { type = string default = "db.t3.medium" }
variable "db_password" { type = string; sensitive = true }
variable "redis_node_type" { type = string default = "cache.t3.medium" }
variable "allowed_cidr_blocks" { type = list(string) default = ["10.0.0.0/8"] }

# ---- RDS PostgreSQL ----
resource "aws_db_subnet_group" "main" {
  name       = "recruitment-db-${var.environment}"
  subnet_ids = var.private_subnet_ids
}

resource "aws_security_group" "rds" {
  name   = "recruitment-rds-sg-${var.environment}"
  vpc_id = var.vpc_id
  ingress { from_port = 5432; to_port = 5432; protocol = "tcp"; cidr_blocks = var.allowed_cidr_blocks }
  egress  { from_port = 0; to_port = 0; protocol = "-1"; cidr_blocks = ["0.0.0.0/0"] }
}

resource "aws_db_instance" "postgresql" {
  identifier             = "recruitment-postgres-${var.environment}"
  engine                 = "postgres"
  engine_version         = "16.1"
  instance_class         = var.db_instance_class
  allocated_storage      = 100
  max_allocated_storage  = 500
  db_name                = "recruitment"
  username               = "recruitment"
  password               = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  multi_az               = var.environment == "prod"
  storage_encrypted      = true
  backup_retention_period = 7
  deletion_protection    = var.environment == "prod"
  skip_final_snapshot    = var.environment != "prod"
  performance_insights_enabled = true
  tags = { Name = "recruitment-postgres-${var.environment}" }
}

# ---- ElastiCache Redis ----
resource "aws_elasticache_subnet_group" "main" {
  name       = "recruitment-redis-${var.environment}"
  subnet_ids = var.private_subnet_ids
}

resource "aws_security_group" "redis" {
  name   = "recruitment-redis-sg-${var.environment}"
  vpc_id = var.vpc_id
  ingress { from_port = 6379; to_port = 6379; protocol = "tcp"; cidr_blocks = var.allowed_cidr_blocks }
  egress  { from_port = 0; to_port = 0; protocol = "-1"; cidr_blocks = ["0.0.0.0/0"] }
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "recruitment-redis-${var.environment}"
  description                = "Redis cluster for AI Recruitment Platform"
  node_type                  = var.redis_node_type
  num_cache_clusters         = var.environment == "prod" ? 2 : 1
  automatic_failover_enabled = var.environment == "prod"
  subnet_group_name          = aws_elasticache_subnet_group.main.name
  security_group_ids         = [aws_security_group.redis.id]
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  tags = { Name = "recruitment-redis-${var.environment}" }
}

output "rds_endpoint" { value = aws_db_instance.postgresql.endpoint; sensitive = true }
output "redis_endpoint" { value = aws_elasticache_replication_group.redis.primary_endpoint_address; sensitive = true }
