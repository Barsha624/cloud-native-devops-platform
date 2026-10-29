# Verification status

An honest record of what has and has not been checked. Update it with your own results as you run things.

## Checked (Linux sandbox, Python 3.13)

- `ruff check .` and `ruff format --check .` pass on all Python files.
- 21 of 22 tests pass. These ran against a throwaway stand-in for `prometheus_client`, because the sandbox could not download packages from PyPI.
- The app was run as a real server: 401 without an API key, 201 with one, 400 on an empty title, `/health` reachable without a key, logs emitted as JSON lines.
- Every YAML file parses.
- A script confirmed the Deployment and Service agree with each other (labels, port name) and that probes, resources and the security context are present.
- A pattern scan found no AWS keys, private keys or hard-coded passwords.

## Not checked: you must run these

| Item | Why it was not checked | What to do |
|---|---|---|
| `test_metrics_count_requests` and the real `prometheus_client` | PyPI unreachable from the sandbox | `pip install -r requirements-dev.txt`, then `pytest`. Expect 22 passed. If the metrics test fails, compare the exact text of the metric line it expects |
| gunicorn startup | not installable in the sandbox | Run the Docker image |
| Docker build, run and HEALTHCHECK | no Docker daemon in the sandbox | `docker build`, `docker run`, `docker ps` should show `healthy` |
| Read-only root filesystem with gunicorn in Kubernetes | needs a cluster | Apply to kind; if pods crash, read `kubectl logs` |
| `kubectl apply -k`, probes, rollouts | no cluster | Follow docs/deployment.md |
| GitHub Actions workflows | never executed; YAML syntax only | Push to GitHub and read the Actions tab. Action version tags (`@v4` etc.) should be confirmed current |
| Helm values, ServiceMonitor, PrometheusRule | no cluster | Check Prometheus Targets page and the Alerts page |
| Terraform | Terraform not installed in the sandbox, so `fmt`, `validate` and `plan` were never run | In `terraform/` run `terraform init`, `terraform fmt -check`, `terraform validate`, `terraform plan` and read the plan carefully |
| EKS module inputs (`~> 20.0`) and VPC module (`~> 5.0`) | module registry unreachable | `terraform validate` will report any renamed input; module changelogs explain differences |
| GitHub OIDC thumbprints and trust policy | not applied | Review the plan; failed role assumption shows in the Actions log |
| Anything in AWS | nothing was created | Cloud steps are optional and written but untested |

## Expected evidence you can collect

See the README section "Verification status and how to produce real evidence".
