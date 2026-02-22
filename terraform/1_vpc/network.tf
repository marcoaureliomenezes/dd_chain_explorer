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
# Public Subnets (for NAT Gateway + Internet-facing resources)
# -----------------------------------------------------------------------
resource "aws_subnet" "public_1" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.cidr_public_subnet_1
  availability_zone       = var.az_public_subnet_1
  map_public_ip_on_launch = true
  tags                    = { Name = "subnet-public-1-dm-chain-explorer" }
}

resource "aws_subnet" "public_2" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.cidr_public_subnet_2
  availability_zone       = var.az_public_subnet_2
  map_public_ip_on_launch = true
  tags                    = { Name = "subnet-public-2-dm-chain-explorer" }
}

# -----------------------------------------------------------------------
# Private Subnets (for ECS Fargate tasks and MSK brokers)
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

resource "aws_subnet" "private_3" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.cidr_private_subnet_3
  availability_zone = var.az_private_subnet_3
  tags              = { Name = "subnet-private-3-dm-chain-explorer" }
}

# -----------------------------------------------------------------------
# Internet Gateway (for public subnets outbound)
# -----------------------------------------------------------------------
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "igw-dm-chain-explorer" }
}

# -----------------------------------------------------------------------
# Elastic IP + NAT Gateway (in public subnet 1, for private subnet outbound)
# -----------------------------------------------------------------------
resource "aws_eip" "nat_eip" {
  domain     = "vpc"
  depends_on = [aws_internet_gateway.igw]
  tags       = { Name = "eip-nat-dm-chain-explorer" }
}

resource "aws_nat_gateway" "nat" {
  allocation_id = aws_eip.nat_eip.id
  subnet_id     = aws_subnet.public_1.id
  depends_on    = [aws_internet_gateway.igw]
  tags          = { Name = "nat-dm-chain-explorer" }
}

# -----------------------------------------------------------------------
# Route Tables
# -----------------------------------------------------------------------
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }
  tags = { Name = "rtb-public-dm-chain-explorer" }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat.id
  }
  tags = { Name = "rtb-private-dm-chain-explorer" }
}

# Public associations
resource "aws_route_table_association" "public_1" {
  subnet_id      = aws_subnet.public_1.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_2" {
  subnet_id      = aws_subnet.public_2.id
  route_table_id = aws_route_table.public.id
}

# Private associations
resource "aws_route_table_association" "private_1" {
  subnet_id      = aws_subnet.private_1.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "private_2" {
  subnet_id      = aws_subnet.private_2.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "private_3" {
  subnet_id      = aws_subnet.private_3.id
  route_table_id = aws_route_table.private.id
}

# -----------------------------------------------------------------------
# Security Groups
# -----------------------------------------------------------------------

# ECS tasks: allow all outbound, restrict inbound within VPC
resource "aws_security_group" "ecs_tasks" {
  name        = "sg-ecs-tasks-dm-chain-explorer"
  description = "Allow outbound internet and internal VPC communication for ECS tasks"
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

# MSK: allow Kafka ports from ECS tasks SG and VPC
resource "aws_security_group" "msk" {
  name        = "sg-msk-dm-chain-explorer"
  description = "Allow Kafka traffic within VPC for MSK cluster"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 9092
    to_port         = 9092
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
    description     = "Kafka plaintext from ECS tasks"
  }

  ingress {
    from_port       = 9094
    to_port         = 9094
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
    description     = "Kafka TLS from ECS tasks"
  }

  ingress {
    from_port       = 9096
    to_port         = 9096
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
    description     = "Kafka IAM auth from ECS tasks"
  }

  ingress {
    from_port   = 2181
    to_port     = 2181
    protocol    = "tcp"
    cidr_blocks = [var.cidr_vpc]
    description = "Zookeeper within VPC"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "sg-msk-dm-chain-explorer" }
}
