resource "aws_vpc" "normabot_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = { Name = "normabot-vpc" }
}

resource "aws_internet_gateway" "normabot_igw" {
  vpc_id = aws_vpc.normabot_vpc.id
  tags   = { Name = "normabot-igw" }
}

resource "aws_subnet" "public_subnet" {
  vpc_id                  = aws_vpc.normabot_vpc.id
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = true
  availability_zone       = "eu-west-1a"

  tags = { Name = "normabot-public-subnet" }
}

resource "aws_route_table" "public_rt" {
  vpc_id = aws_vpc.normabot_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.normabot_igw.id
  }

  tags = { Name = "normabot-public-rt" }
}

resource "aws_route_table_association" "public_assoc" {
  subnet_id      = aws_subnet.public_subnet.id
  route_table_id = aws_route_table.public_rt.id
}