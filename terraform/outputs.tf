output "ecr_repository_url" {
  description = "Registry URL to push images to."
  value       = aws_ecr_repository.taskapi.repository_url
}

output "github_actions_role_arn" {
  description = "Set this as the AWS_ROLE_ARN repository variable in GitHub."
  value       = aws_iam_role.github_ecr_push.arn
}
