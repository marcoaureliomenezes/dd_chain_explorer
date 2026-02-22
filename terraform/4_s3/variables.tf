variable "region" {
  default = "sa-east-1"
}
variable "environment" {
  default = "prod"
}
variable "raw_bucket_name" {
  default = "dm-chain-explorer-raw-data"
  type    = string
}
variable "lakehouse_bucket_name" {
  default = "dm-chain-explorer-lakehouse"
  type    = string
}
