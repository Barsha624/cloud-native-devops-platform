# Security

This is a learning project. These are the controls it includes, why they matter, and what is still missing. No security audit has been performed.

## Controls in place

| Area | Control | Why |
|---|---|---|
| Secrets | No credentials in the repository; `.gitignore` and `.dockerignore` exclude `.env`, keys, `*.tfstate`, `*.tfvars` | Anything committed to Git stays in its history |
| Secrets | `API_KEY` comes from an environment variable, from a Kubernetes Secret in the cluster | Config separate from code |
| Auth | Optional `X-API-Key` check using constant-time comparison (`hmac.compare_digest`) | Avoids leaking key contents through response timing |
| Container | Runs as non-root user (UID 10001) | A compromised process has fewer rights |
| Container | Read-only root filesystem, all Linux capabilities dropped, no privilege escalation, `RuntimeDefault` seccomp profile | Shrinks what an attacker can do after a break-in |
| Container | Slim base image, multi-stage build, no build tools in the runtime image | Smaller attack surface |
| Errors | Unexpected errors return a generic message; details go only to logs | No internal details leaked to clients |
| CI | Dependency audit (pip-audit) and image scan (Trivy), both report-only at first | Finds known vulnerabilities |
| CI | Workflow permissions limited to `contents: read` | Least privilege for the pipeline |
| AWS | GitHub authenticates through OIDC with short-lived tokens, no stored access keys | Nothing long-lived to leak |
| AWS | IAM role can only be assumed from `main` of one named repository, and can only push to one ECR repository | Least privilege |
| AWS | ECR tags immutable, scan on push | A tag cannot be silently replaced |
| AWS | EKS API reachable only from your IP | Not open to the internet |
| Supply chain | Dependabot for pip, Actions and Docker | Keeps dependencies current |

## Known weaknesses

- The API key is one shared value; there are no users, roles or rate limiting.
- No TLS in this project. In a real setup, terminate TLS at an ingress or load balancer.
- A Kubernetes Secret is base64-encoded, not encrypted, unless encryption at rest is configured.
- Image tags in `FROM` are not pinned by digest; Actions are pinned to major versions, not commit SHAs.
- Trivy and pip-audit do not fail the build yet.
- No NetworkPolicies, no admission policies, no image signing.
- EKS worker nodes are in public subnets to avoid NAT cost, which is a deliberate trade-off.

## If you accidentally commit a secret

Treat it as compromised. Rotate or delete the credential first, then clean Git history. Removing it in a later commit is not enough.

## How to check for yourself

- `pip-audit -r requirements.txt` for dependency advisories
- Trivy scan output in the CI run
- `docker run --rm taskapi:local id` should show UID 10001, not root
- `kubectl -n taskapi get pod <name> -o yaml` to review the applied security context
