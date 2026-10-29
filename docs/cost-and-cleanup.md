# Cost and cleanup

Prices change and differ by region. Check the AWS pricing pages and the AWS Billing console yourself. This guide lists what creates cost, not what it costs today.

**Before any AWS work:** set up a budget alert (Billing console, Budgets) so you hear about unexpected spend. Check the free-tier status of each service; a free tier may be limited, time-limited or not apply to your account.

## What each stage costs

| Stage | Creates in AWS | Cost drivers |
|---|---|---|
| Local app, tests, Docker, kind, local monitoring | nothing | none (your own electricity and disk) |
| `terraform/` (ECR + IAM) | ECR repository, IAM role, OIDC provider | ECR charges for stored image data (per GB-month) and data transfer out. IAM and the OIDC provider have no charge. Image scanning on push may have its own pricing, so check. |
| `terraform/eks/` | VPC, EKS cluster, EC2 node, security groups, KMS key | EKS control plane hourly fee; EC2 instance hours; EBS volume; public IPv4 addresses (charged hourly); KMS key monthly fee; data transfer. Running an older Kubernetes version can move the cluster into paid extended support. |

Things deliberately avoided to save money: no NAT gateway, no load balancer (use `kubectl port-forward`), control-plane logging off, one small node.

Things that quietly cost money if you add them: a Service of type `LoadBalancer` (creates an AWS load balancer), extra nodes, leaving the cluster running overnight, CloudWatch logs.

## Cleanup procedures

**Local**
- `kind delete cluster --name taskapi`
- `helm uninstall monitoring -n monitoring` (only if you keep the cluster)
- `docker system prune` removes unused images and containers (review the prompt first)

**ECR + IAM stack** (run where you ran `terraform apply`)
```
cd terraform
terraform destroy
```
`ecr_force_delete` defaults to `true` so images do not block the destroy. Afterwards, confirm in the console that the ECR repository, the `taskapi-github-ecr-push` role, and (if created) the GitHub OIDC provider are gone.

**EKS stack**
```
kubectl delete namespace taskapi
cd terraform/eks
terraform destroy
```
Delete the namespace first so nothing created from inside Kubernetes (such as a load balancer) is left behind to block the VPC deletion. Afterwards check the console for leftovers: EC2 instances, load balancers, EBS volumes, Elastic IPs, KMS keys (scheduled for deletion, which takes days), CloudWatch log groups.

**If Terraform state is lost:** delete resources manually by name, starting with the EKS cluster and node group, then load balancers, then the VPC.

## Rule of thumb

Create, learn, destroy in the same session. Anything left running is billed whether you use it or not.
