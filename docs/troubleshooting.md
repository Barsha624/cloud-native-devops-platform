# Troubleshooting

Start with: what did you expect, what happened, and what does the exact error text say. Read the error; it usually names the problem.

## Python and local setup

| Symptom | Likely cause | Fix |
|---|---|---|
| `running scripts is disabled` | PowerShell execution policy | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `No module named flask` | venv not active or dependencies not installed | Activate `.venv`, run `pip install -r requirements-dev.txt` |
| `No module named taskapi` | run from the wrong folder | Run from the repo root; pytest finds it through `pyproject.toml` |
| `Address already in use` | port 5000 is taken | `$env:PORT = "5001"` |
| `ruff format --check` fails | formatting differs | Run `ruff format .` and commit |

## Docker

| Symptom | Cause | Fix |
|---|---|---|
| `Cannot connect to the Docker daemon` | Docker Desktop not running | Start it and wait until it says running |
| Container exits immediately | app crashed on start | `docker logs <container>` |
| Works in the container but not from your browser | missing `-p 5000:5000` | Add the port mapping |
| `permission denied` writing a file | non-root user, read-only filesystem | Write to `/tmp` only |

Useful: `docker ps -a`, `docker logs`, `docker exec -it <container> sh`.

## Kubernetes

Always begin with three commands:

```
kubectl -n taskapi get pods
kubectl -n taskapi describe pod <name>
kubectl -n taskapi logs <name>
```

| Status | Meaning | Check |
|---|---|---|
| `ErrImagePull` / `ImagePullBackOff` | image not found or not loaded | For kind, run `kind load docker-image`; check the tag spelling |
| `CrashLoopBackOff` | container starts then dies | `kubectl logs <pod> --previous` |
| `Running` but `0/1` ready | readiness probe failing | `describe pod`, look at probe events; check `/health` |
| `Pending` | cluster lacks resources | `describe pod`, read the Events at the bottom |
| `OOMKilled` | exceeded the 128Mi memory limit | raise the limit, or find the leak |
| Service reachable by port-forward but not otherwise | Service is `ClusterIP` | Expected; use port-forward |
| Changed Secret not picked up | env vars are read at start | `kubectl rollout restart deployment/taskapi` |

## CI

- Failure in `lint`: run the same `ruff` commands locally.
- Failure in `docker` smoke test: the step prints the container logs.
- `publish-ecr` fails at the AWS login: check the `AWS_ROLE_ARN`, `AWS_REGION` and `ECR_REPOSITORY` variables, that the workflow ran on `main`, and that `github_repository` in the Terraform variables matches `OWNER/REPO` exactly, including case.

## Terraform

| Symptom | Fix |
|---|---|
| `EntityAlreadyExists` for the OIDC provider | Another project created it; set `create_github_oidc_provider = false` |
| `RepositoryNotEmptyException` on destroy | Keep `ecr_force_delete = true` or delete the images first |
| Credentials errors | In CloudShell you are already authenticated; locally use `aws sso login` |
| Plan wants to destroy something unexpected | Stop. Do not apply. Work out why first |

## Monitoring

- Target missing in Prometheus: the ServiceMonitor must be applied after the Helm install, and the Service port must be named `http`.
- Metrics empty: send some requests first; counters only appear after traffic.
- Monitoring pods pending: Docker Desktop needs more memory.
