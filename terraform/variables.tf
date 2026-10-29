variable "aws_region" {
  description = "AWS region for all resources. Pick the region you already use."
  type        = string
  default     = "ap-south-1"
}

variable "github_repository" {
  description = "GitHub repository allowed to push images, as OWNER/REPO."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$", var.github_repository))
    error_message = "Use the form OWNER/REPO, for example my-user/cloud-native-devops-platform."
  }
}

variable "ecr_repository_name" {
  description = "Name of the ECR repository."
  type        = string
  default     = "taskapi"
}

variable "create_github_oidc_provider" {
  description = "Create the GitHub OIDC identity provider. An AWS account can have only one; set false if it already exists."
  type        = bool
  default     = true
}

variable "ecr_force_delete" {
  description = "Delete the repository even if it contains images. True suits a learning project; set false for anything you care about."
  type        = bool
  default     = true
}

variable "images_to_keep" {
  description = "How many recent images ECR keeps. Older ones are deleted to limit storage cost."
  type        = number
  default     = 10
}
