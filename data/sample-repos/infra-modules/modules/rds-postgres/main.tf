# PLANTED ISSUE (golden-set positive case for structural doc-drift):
# this comment claims encryption is disabled, but the resource below
# actually provisions storage_encrypted = true. The comment is stale.
# Comment claims: "encryption disabled by default for this module"
resource "aws_db_instance" "postgres" {
  engine            = "postgres"
  engine_version    = "15.4"
  instance_class    = var.instance_class
  allocated_storage = 20
  storage_encrypted = true
  username          = var.username
  password          = var.password
  skip_final_snapshot = true
}

variable "instance_class" {
  type    = string
  default = "db.t3.micro"
}

variable "username" {
  type      = string
  sensitive = true
}

variable "password" {
  type      = string
  sensitive = true
}
