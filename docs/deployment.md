# Deployment guide

Work through the stages in order. Stages 1 to 4 are free and local. Stage 5 (AWS) is optional and can cost money; read [cost-and-cleanup.md](cost-and-cleanup.md) first. Commands are for Windows PowerShell unless stated.

## 1. Run and test the app

See the README. Expected: `pytest` reports all tests passed, `ruff check .` reports no problems.

## 2. Build and run the container

```powershell
docker build -t taskapi:local --build-arg APP_VERSION=local .
docker run --rm -p 5000:5000 taskapi:local
```

In another window: `Invoke-RestMethod http://127.0.0.1:5000/version` should return `local`.

Why `-p 5000:5000`: the container has its own network. This maps your machine's port 5000 to the container's port 5000. The app inside listens on `0.0.0.0` so it accepts connections arriving from outside the container.

To test the API key:

```powershell
docker run --rm -p 5000:5000 -e API_KEY="local-test-value" taskapi:local
Invoke-RestMethod http://127.0.0.1:5000/tasks -Headers @{ "X-API-Key" = "local-test-value" }
```

## 3. Local Kubernetes with kind

kind runs a Kubernetes cluster inside Docker containers. It costs nothing but needs Docker Desktop to have a few GB of memory.

```powershell
kind create cluster --name taskapi
docker build -t taskapi:local --build-arg APP_VERSION=local .
kind load docker-image taskapi:local --name taskapi
kubectl apply -k k8s/base
kubectl -n taskapi rollout status deployment/taskapi
kubectl -n taskapi get pods,svc
```

Expected: two pods `Running` and `1/1` ready. A Service has no public address here, so forward a port:

```powershell
kubectl -n taskapi port-forward svc/taskapi 8080:80
```

Leave it running and use `http://127.0.0.1:8080` from another window.

### Add the Secret (API key)

```powershell
$bytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$key = [Convert]::ToBase64String($bytes)
kubectl -n taskapi create secret generic taskapi-secret --from-literal=API_KEY="$key"
kubectl -n taskapi rollout restart deployment/taskapi
```

Pods read environment variables only at startup, which is why the restart is needed. Do not paste `$key` into chat, files or Git.

### Look at probes and resources

```powershell
kubectl -n taskapi describe pod -l app=taskapi
```

Find the `Liveness`, `Readiness`, `Limits` and `Requests` lines. Readiness decides whether the pod receives traffic; liveness decides whether Kubernetes restarts it.

## 4. Rollouts and rollback

```powershell
docker build -t taskapi:v2 --build-arg APP_VERSION=v2 .
kind load docker-image taskapi:v2 --name taskapi
kubectl -n taskapi set image deployment/taskapi taskapi=taskapi:v2
kubectl -n taskapi rollout status deployment/taskapi
kubectl -n taskapi rollout history deployment/taskapi
```

Roll back:

```powershell
kubectl -n taskapi rollout undo deployment/taskapi
```

Practise a failed deployment: point at an image that does not exist.

```powershell
kubectl -n taskapi set image deployment/taskapi taskapi=taskapi:does-not-exist
kubectl -n taskapi get pods
kubectl -n taskapi rollout undo deployment/taskapi
```

Expected: new pods show `ErrImagePull` or `ImagePullBackOff`, while the old pods keep serving because `maxUnavailable` is 0. The undo restores the last working version.

Delete the cluster when finished: `kind delete cluster --name taskapi`.

## 5. Monitoring (local)

```powershell
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install monitoring prometheus-community/kube-prometheus-stack -n monitoring --create-namespace -f monitoring/values-kind.yaml
kubectl -n monitoring get pods
kubectl apply -f monitoring/servicemonitor.yaml
```

Wait until the monitoring pods are `Running`, then:

```powershell
kubectl -n monitoring port-forward svc/monitoring-kube-prometheus-prometheus 9090:9090
```

Open http://127.0.0.1:9090, go to Status, then Targets, and look for `taskapi`. Useful queries:

- Requests per second by route: `sum(rate(http_requests_total[1m])) by (endpoint)`
- 95th percentile latency: `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))`

Grafana:

```powershell
kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80
```

Username `admin`; the generated password is in the `monitoring-grafana` secret in the `monitoring` namespace (see the comment at the top of `monitoring/values-kind.yaml`; decode the base64 value). Build a panel from the queries above. No dashboard JSON is committed yet (see roadmap).

Remove monitoring: `helm uninstall monitoring -n monitoring`, then `kubectl delete namespace monitoring`. Helm leaves the CRDs behind; deleting the kind cluster removes everything.

## 6. Optional: AWS with Terraform (can cost money)

This stage creates an ECR repository and an IAM role. The charges are small but real; see the cost guide. It does not touch your existing Finova EC2 deployment.

### Safe way to run Terraform: AWS CloudShell

CloudShell runs in your browser with your console login, so you do not create long-lived access keys. In CloudShell:

```bash
sudo dnf install -y dnf-plugins-core
sudo dnf config-manager --add-repo https://rpm.releases.hashicorp.com/AmazonLinux/hashicorp.repo
sudo dnf install -y terraform
git clone https://github.com/<you>/cloud-native-devops-platform.git
cd cloud-native-devops-platform/terraform
cp terraform.tfvars.example terraform.tfvars   # then edit with nano
terraform init
terraform plan
```

Read the plan. It should list about 6 resources to add and nothing to change or destroy. Only then:

```bash
terraform apply
```

Keep `terraform.tfstate` safe. CloudShell storage can be deleted after a long period of inactivity, which would leave resources that Terraform no longer knows about. Note the resource names so you can delete them by hand if that happens.

Then in GitHub: Settings, Secrets and variables, Actions, Variables tab. Add `AWS_ROLE_ARN` (from the Terraform output), `AWS_REGION`, and `ECR_REPOSITORY` (`taskapi`). These are not secrets. Run the "Publish image to ECR" workflow manually from the Actions tab.

Clean up:

```bash
terraform destroy
```

### Optional: EKS

Do not do this casually. An EKS cluster has hourly charges for the control plane and for the worker nodes, and other add-on resources. Read the cost guide, fill in `terraform/eks/terraform.tfvars` (a supported Kubernetes version and your own public IP), then:

```bash
cd terraform/eks
terraform init
terraform plan
terraform apply
aws eks update-kubeconfig --region <region> --name taskapi-eks
```

Deploy:

```bash
cd ../../k8s/base
kustomize edit set image taskapi=<account>.dkr.ecr.<region>.amazonaws.com/taskapi:<commit-sha>
kubectl apply -k .
kubectl -n taskapi port-forward svc/taskapi 8080:80
```

Always tear down in this order, and check the AWS console afterwards:

```bash
kubectl delete namespace taskapi
cd ../../terraform/eks
terraform destroy
```
