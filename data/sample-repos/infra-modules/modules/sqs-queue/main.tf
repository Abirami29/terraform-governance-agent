# PLANTED ISSUE (golden-set positive case for find_unused_modules):
# no repo in data/sample-repos consumes this module — should show up
# as an orphan / zero-consumer module.
resource "aws_sqs_queue" "this" {
  name = var.name
}

variable "name" {
  type = string
}
