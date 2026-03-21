resource "aws_vpc" "main" {
  cidr_block           = var.cidr_vpc
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(var.common_tags, { Name = "${var.name_prefix}-vpc-${var.environment}" })
}

resource "aws_subnet" "public_1" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.cidr_public_subnet_1
  availability_zone       = var.az_public_subnet_1
  map_public_ip_on_launch = true
  tags                    = merge(var.common_tags, { Name = "${var.name_prefix}-subnet-public-1-${var.environment}" })
}

resource "aws_subnet" "private_1" {
  count             = var.enable_private_subnets ? 1 : 0
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.cidr_private_subnet_1
  availability_zone = var.az_private_subnet_1
  tags              = merge(var.common_tags, { Name = "${var.name_prefix}-subnet-private-1-${var.environment}" })
}

resource "aws_subnet" "private_2" {
  count             = var.enable_private_subnets ? 1 : 0
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.cidr_private_subnet_2
  availability_zone = var.az_private_subnet_2
  tags              = merge(var.common_tags, { Name = "${var.name_prefix}-subnet-private-2-${var.environment}" })
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
  tags   = merge(var.common_tags, { Name = "${var.name_prefix}-igw-${var.environment}" })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }
  tags = merge(var.common_tags, { Name = "${var.name_prefix}-rtb-public-${var.environment}" })
}

resource "aws_route_table_association" "public_1" {
  subnet_id      = aws_subnet.public_1.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  count  = var.enable_private_subnets ? 1 : 0
  vpc_id = aws_vpc.main.id
  tags   = merge(var.common_tags, { Name = "${var.name_prefix}-rtb-private-${var.environment}" })
}

resource "aws_route_table_association" "private_1" {
  count          = var.enable_private_subnets ? 1 : 0
  subnet_id      = aws_subnet.private_1[0].id
  route_table_id = aws_route_table.private[0].id
}

resource "aws_route_table_association" "private_2" {
  count          = var.enable_private_subnets ? 1 : 0
  subnet_id      = aws_subnet.private_2[0].id
  route_table_id = aws_route_table.private[0].id
}

resource "aws_vpc_endpoint" "s3" {
  count             = var.enable_s3_endpoint ? 1 : 0
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids = concat(
    [aws_route_table.public.id],
    var.enable_private_subnets ? [aws_route_table.private[0].id] : []
  )
  tags = merge(var.common_tags, { Name = "${var.name_prefix}-vpce-s3-${var.environment}" })
}

resource "aws_security_group" "ecs_tasks" {
  name        = "${var.name_prefix}-ecs-tasks-${var.environment}"
  description = "ECS Fargate tasks - outbound open, inbound VPC-only"
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

  tags = merge(var.common_tags, { Name = "${var.name_prefix}-sg-ecs-tasks-${var.environment}" })
}
