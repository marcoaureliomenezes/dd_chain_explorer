# -----------------------------------------------------------------------
# VPC
# -----------------------------------------------------------------------
resource "aws_vpc" "main" {
  cidr_block           = var.cidr_vpc
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "vpc-dm-chain-explorer" }
}

# -----------------------------------------------------------------------
# Public Subnet — ECS Fargate tasks (assign_public_ip = true, sem NAT GW)
# -----------------------------------------------------------------------
resource "aws_subnet" "public_1" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.cidr_public_subnet_1
  availability_zone       = var.az_public_subnet_1
  map_public_ip_on_launch = true
  tags                    = { Name = "subnet-public-1-dm-chain-explorer" }
}

# -----------------------------------------------------------------------
# Private Subnets — Databricks workspace (2 AZs, sem acesso à internet)
# -----------------------------------------------------------------------
resource "aws_subnet" "private_1" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.cidr_private_subnet_1
  availability_zone = var.az_private_subnet_1
  tags              = { Name = "subnet-private-1-dm-chain-explorer" }
}

resource "aws_subnet" "private_2" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.cidr_private_subnet_2
  availability_zone = var.az_private_subnet_2
  tags              = { Name = "subnet-private-2-dm-chain-explorer" }
}

# -----------------------------------------------------------------------
# Internet Gateway + Route Table public
# -----------------------------------------------------------------------
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "igw-dm-chain-explorer" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }
  tags = { Name = "rtb-public-dm-chain-explorer" }
}

resource "aws_route_table_association" "public_1" {
  subnet_id      = aws_subnet.public_1.id
  route_table_id = aws_route_table.public.id
}

# -----------------------------------------------------------------------
# Private Route Table — MSK brokers e subnets Databricks (sem internet)
# -----------------------------------------------------------------------
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
  tags   = merge(local.common_tags, { Name = "rtb-private-dm-chain-explorer" })
}

resource "aws_route_table_association" "private_1" {
  subnet_id      = aws_subnet.private_1.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "private_2" {
  subnet_id      = aws_subnet.private_2.id
  route_table_id = aws_route_table.private.id
}

# -----------------------------------------------------------------------
# S3 VPC Gateway Endpoint — roteia tráfego S3 pelas subnets privadas/públicas
# sem precisar de NAT GW. Obrigatório para Databricks (is_no_public_ip_enabled).
# -----------------------------------------------------------------------
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.public.id, aws_route_table.private.id]
  tags              = merge(local.common_tags, { Name = "vpce-s3-dm-chain-explorer" })
}

# -----------------------------------------------------------------------
# Security Groups
# -----------------------------------------------------------------------

# ECS tasks (subnet pública) — todo egress liberado; ingress somente VPC-local
resource "aws_security_group" "ecs_tasks" {
  name        = "ecs-tasks-dm-chain-explorer"
  description = "ECS Fargate tasks - outbound livre, inbound apenas VPC"
  vpc_id      = aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [var.cidr_vpc]
  }

  tags = { Name = "sg-ecs-tasks-dm-chain-explorer" }
}

