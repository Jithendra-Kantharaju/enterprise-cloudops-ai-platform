# Enterprise CloudOps AI Platform

An end-to-end **DevOps + AIOps** platform: a seven-service e-commerce microservices
application deployed on **AWS EKS**, provisioned with **Terraform**, delivered through a
**GitHub Actions** CI/CD pipeline and **ArgoCD** GitOps, observed with
**Prometheus + Grafana**, and operated by an **AI incident-diagnosis assistant ("Kira")**
built on **AWS Bedrock**.

<p align="center">
  <img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/Architecture_image.png" alt="Enterprise CloudOps AI Platform architecture" width="940">
</p>

This repository takes an application from a local Docker Compose setup all the way to a
self-healing, observable, AI-assisted production platform on Kubernetes.

---

## What this project demonstrates

- **Infrastructure as Code:** entire AWS footprint (VPC, EKS, node groups, ECR, IAM, add-ons) defined in modular Terraform.
- **Container orchestration:** microservices packaged as Docker images and run on a managed Kubernetes (EKS) cluster.
- **CI/CD:** GitHub Actions builds and pushes seven service images to ECR in parallel and updates the deployment manifests.
- **GitOps:** ArgoCD continuously reconciles the cluster to the Git-declared state (self-healing, drift detection).
- **Observability:** every service exposes `/metrics`; Prometheus scrapes them, Grafana visualises them, Fluent Bit ships logs to CloudWatch.
- **AIOps:** a Bedrock agent answers natural-language questions ("are any services down?") by calling Lambda tools that read live logs, metrics, and cluster health, then returns a root-cause diagnosis.

---

## Demo video

A short walkthrough of the platform and the Kira AIOps assistant diagnosing a live incident:

<p align="center">
  <a href="https://youtu.be/REPLACE_WITH_YOUR_VIDEO_ID">
    <img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/devops-aiops-UI-3.0.png" alt="Watch the AIOps demo" width="800">
  </a>
</p>

> Replace `REPLACE_WITH_YOUR_VIDEO_ID` with your uploaded YouTube link.

---

## Architecture

```mermaid
flowchart TB
    user([User / Engineer])

    subgraph AWS["AWS (us-east-1)"]
        subgraph EKS["EKS Cluster"]
            fe["Frontend (React + nginx)"]
            gw["API Gateway"]
            subgraph svc["Backend Microservices"]
                auth["auth"]
                prod["product-service"]
                ordsvc["order-service"]
                ords["orders"]
                usr["user-service"]
            end
            pg[("PostgreSQL\nauth/products/orders/users DBs")]
            subgraph mon["Monitoring"]
                prom["Prometheus"]
                graf["Grafana"]
            end
            argo["ArgoCD"]
            fb["Fluent Bit"]
        end
        ecr["ECR (7 image repos)"]
        cw["CloudWatch Logs"]
        subgraph bedrock["AIOps"]
            agent["Bedrock Agent 'Kira' (Nova Lite)"]
            l1["Lambda: fetch_logs"]
            l2["Lambda: fetch_metrics"]
            l3["Lambda: fetch_health"]
        end
    end

    gh["GitHub Actions CI"] -->|build + push| ecr
    gh -->|update image tags| argo
    argo -->|sync| EKS

    user -->|shops| fe --> gw --> svc --> pg
    svc -->|/metrics| prom --> graf
    fb -->|pod logs| cw

    user -->|chat| streamlit["Streamlit UI"] --> agent
    agent --> l1 --> cw
    agent --> l2 --> prom
    agent --> l3 --> EKS
```

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Application | React, Node.js / TypeScript, PostgreSQL |
| Containers | Docker, Docker Compose |
| Orchestration | Kubernetes (AWS EKS 1.34) |
| Infrastructure | Terraform (modular: VPC, EKS, ECR, ArgoCD) |
| CI/CD | GitHub Actions (parallel matrix build) |
| Registry | Amazon ECR |
| GitOps | ArgoCD + Kustomize |
| Metrics | Prometheus (kube-prometheus-stack) |
| Dashboards | Grafana |
| Log forwarding | AWS Fluent Bit to CloudWatch |
| AIOps | AWS Bedrock Agent (Amazon Nova Lite) + Lambda action groups |
| AI UI | Streamlit |

---

## Screenshots

### Application and delivery

<table>
  <tr>
    <td width="50%"><b>Storefront (React frontend)</b><br><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/devops-aiops-app.png" width="440"></td>
    <td width="50%"><b>ECR: 7 image repositories</b><br><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/devops-aiops-AWS.png" width="440"></td>
  </tr>
  <tr>
    <td width="50%"><b>ArgoCD: synced application tree</b><br><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/devops-aiops-argocd1.png" width="440"></td>
    <td width="50%"><b>ArgoCD: application overview</b><br><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/devops-aiops-argocd2.png" width="440"></td>
  </tr>
</table>

### Observability

<table>
  <tr>
    <td width="50%"><b>Grafana: live service dashboard</b><br><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/devops-aiops-grafana1.png" width="440"></td>
    <td width="50%"><b>Prometheus: scrape targets UP</b><br><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/devops-aiops-Prometheus.png" width="440"></td>
  </tr>
</table>

### AIOps assistant "Kira"

Kira reasons like an SRE: it queries live logs, metrics, and cluster health through Lambda
tools, then answers in plain language. The sequence below shows it confirming a healthy
cluster, listing running services, and then correctly detecting a service that was
deliberately scaled to zero.

<p align="center"><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/devops-aiops-UI.png" width="800"></p>
<p align="center"><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/devops-aiops-UI-2.0.png" width="800"></p>
<p align="center"><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/devops-aiops-UI-3.0.png" width="800"></p>

---

## How it works (by layer)

**Application.** Seven services (a React frontend, an API gateway, and `auth`,
`product-service`, `order-service`, `orders`, and `user-service`) backed by PostgreSQL.
Each service owns its own database (the data-ownership pattern); the gateway is the single
entry point and routes requests to the right service.

**Build and ship.** A push to `main` triggers GitHub Actions, which builds all seven
images in parallel and pushes them to ECR, then rewrites the image tags in `gitops/k8s/`.

**Deliver.** ArgoCD watches `gitops/` and reconciles the cluster to match Git. Manual
changes (such as scaling a deployment by hand) are detected as drift and, with self-heal
enabled, reverted automatically.

**Observe.** Every backend exposes a `/metrics` endpoint; a `ServiceMonitor` tells
Prometheus to scrape it. Grafana ships a pre-loaded dashboard, and Fluent Bit runs as a
DaemonSet forwarding pod logs to CloudWatch.

**Diagnose with AI.** "Kira" is a Bedrock agent. When asked a question it decides which
tools to call (three Lambda functions reading CloudWatch logs, Prometheus metrics, and EKS
health), correlates the results, and returns a root cause plus remediation steps. A
Streamlit chat UI sits on top.

---

## Deploy it yourself

Full instructions are in [`projects/README.md`](projects/README.md). High level:

1. **Local:** build the React frontend, then `docker compose up -d --build` in `projects/boutique-microservices/`.
2. **Infra:** `terraform init && terraform apply` in `projects/Infrastructure/`.
3. **Images:** run the GitHub Actions pipeline (or build/push manually) to populate ECR.
4. **Deploy:** `kubectl apply -k gitops/`, then run the DB restore job.
5. **GitOps:** `kubectl apply -f gitops/argo-cd.yml -n argocd`.
6. **AIOps (optional):** install Fluent Bit, deploy the three Lambdas + Bedrock agent (`projects/aiops-assistant/`), run the Streamlit UI.

> Cost: EKS, an on-demand node, and a LoadBalancer bill hourly. Run `terraform destroy`
> and remove the LoadBalancer / Bedrock / Lambda resources when done.

---

## Repository structure

```
enterprise-cloudops-ai-platform/
├── projects/
│   ├── boutique-microservices/    # The application (7 services + Postgres)
│   ├── Infrastructure/            # Terraform modules for AWS / EKS
│   └── aiops-assistant/           # Bedrock agent "Kira", Lambdas, Streamlit UI
├── gitops/
│   ├── argo-cd.yml                # ArgoCD Application manifest
│   ├── kustomization.yml          # Kustomize entry point
│   └── k8s/                       # Deployments, Services, StatefulSet, ServiceMonitor
├── Docs/
│   ├── Project.md                 # Detailed walkthrough + interview prep
│   ├── Architecture_image.png     # Architecture diagram
│   └── *.png                      # Demo screenshots
└── .github/workflows/ci.yml       # CI pipeline (build, push, update manifests)
```

A detailed component-by-component walkthrough and interview-prep guide lives in
[`Docs/Project.md`](Docs/Project.md).

---

## Troubleshooting and lessons learned

Real problems hit during deployment and how they were resolved.

| Symptom | Root cause | Fix |
|---------|-----------|-----|
| `terraform apply` -> `Error: Unauthorized` | Short-lived EKS auth token expired during the long cluster build | Re-run apply (fresh token), or use an `exec` plugin (`aws eks get-token`) |
| Pods stuck in `InvalidImageName` | Manifests still held the literal `<AWS_ACCOUNT_ID>` placeholder | Substituted the real account ID; pushed images to ECR first |
| `auth`/`orders` crash-looping (`3D000`) | In Kubernetes, Postgres starts empty (no auto-run init scripts) | Ran the database restore Job to create and seed the four databases |
| Fluent Bit `NoCredentialProviders` | Node IMDS hop limit of 1 blocked pods from reaching metadata | Raised the hop limit to 2 via `modify-instance-metadata-options` |
| Agent reported "all healthy" after scaling a service to 0 | Smaller model reused the previous tool result instead of re-fetching | Forced a fresh tool call (new session / explicit re-check) |
| `kubectl scale --replicas=0` instantly reverted | ArgoCD self-heal reconciled the drift back to Git state | GitOps working as intended; disable auto-sync to test failure scenarios |
| Windows / Git Bash path mangling | MSYS auto-converts leading-slash arguments | `export MSYS_NO_PATHCONV=1`, `pwd -W`, and `python` instead of `python3` |

---

## Acknowledgements

Built by following and adapting a DevOps + AIOps tutorial series, then debugged and
extended end-to-end on real AWS infrastructure.