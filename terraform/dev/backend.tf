terraform {
  backend "s3" {
    bucket  = "nash-terraform-state-059623506914"
    key     = "nash/dev/terraform.tfstate"
    region  = "us-west-2"
    encrypt = true
  }
}
