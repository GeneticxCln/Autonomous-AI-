# Kubernetes Deployment Pack

Production manifests for the Autonomous Agent platform live in this directory. They
are organized so you can apply everything with a single `kustomize` invocation and
extend per-environment overlays later.

## Layout

```
k8s/
├── kustomization.yaml           # Base bundle (namespace + workloads)
├── namespace/                   # Namespace definition
├── configmaps/                  # Application + Redis parameters
├── secrets/                     # Runtime secrets (JWT, API salts, etc.)
├── deployments/                 # API, worker, Redis, PVCs, HPAs
├── services/                    # ClusterIP services for API/Redis
├── ingress/                     # Istio/Ingress routing
├── security/                    # Peer authentication defaults
└── istio/                       # Optional mesh operator + gateway config
```

## Quick Start

```bash
# Ensure secrets contain real values first
kubectl apply -k k8s

# Tail rollouts
kubectl rollout status deploy/agent-api -n agent-system
kubectl get pods -n agent-system
```

The bundled `kustomization.yaml` wires together ConfigMaps, Secrets, Deployments,
Services, HPAs, and the namespace so you get a working stack immediately.

## Horizontal Scaling & HPA

- The API deployment ships with 3 replicas and an autoscaler (`agent-api-hpa`)
  that grows between 2–10 pods based on CPU (70%) and memory (80%) utilization.
- The worker deployment starts with 2 replicas and an autoscaler
  (`agent-worker-hpa`) that targets the `agent-worker` deployment (fixed from the
  previous `agent-worker-normal` typo). It scales 2–8 pods on CPU (60%) and memory
  (70%) so background execution keeps pace with queue depth.
- Use `kubectl get hpa -n agent-system` to watch scaling decisions and adjust
  `metrics` / `behavior` thresholds per cluster.

## Secrets & Configuration

- Application secrets live in `secrets/agent-secrets.yaml`. Replace the placeholder
  strings before deploying or generate them via your secret manager and reference
  them with `secretGenerator` if preferred.
- Configurable knobs (database URLs, Redis, tracing flags, etc.) reside in
  `configmaps/agent-config.yaml`; tune those to match your target environment.

## Service Mesh Integration

Optional Istio artifacts (`istio/istio-config.yaml`, `istio/gateway.yaml`) provide
service mesh installation plus ingress routing, tracing, and MTLS defaults. Apply
them after installing Istio:

```bash
kubectl apply -f k8s/istio/istio-config.yaml
kubectl apply -f k8s/istio/gateway.yaml
```

## Day-2 Operations

- `kubectl top pods -n agent-system` to confirm replica resource pressure.
- `kubectl describe hpa agent-api-hpa -n agent-system` for scaling history.
- Update container images by pushing a new tag and editing the deployment image
  fields (or image pull secret) once CI/CD is wired up.
