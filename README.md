# Enterprise CloudOps AI Platform

An end-to-end **DevOps + AI** platform on **AWS EKS**: a seven-service e-commerce
microservices application plus a **customer-facing AI shopping assistant**, provisioned
with **Terraform**, delivered through a **GitHub Actions** CI pipeline and **ArgoCD**
GitOps, and observed with **Prometheus + Grafana**. The AI assistant is a
Retrieval-Augmented-Generation (RAG) service built with **FastAPI + ChromaDB + OpenAI**.

<p align="center">
  <img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/AI_Archtecture.png" alt="Enterprise CloudOps AI Platform architecture" width="960">
</p>

This repository takes an application from a local Docker Compose setup all the way to a
self-healing, observable, AI-assisted platform running live on Kubernetes.

---

## What this project demonstrates

- **Infrastructure as Code:** entire AWS footprint (VPC, EKS, node groups, ECR, IAM, add-ons) defined in modular Terraform.
- **Container orchestration:** eight microservices packaged as Docker images and run on a managed Kubernetes (EKS) cluster.
- **CI/CD:** GitHub Actions builds and pushes eight service images to ECR in parallel and updates the deployment manifests.
- **GitOps:** ArgoCD continuously reconciles the cluster to the Git-declared state (self-healing, drift detection).
- **Observability:** every service exposes `/metrics`; Prometheus scrapes them and Grafana visualises them.
- **Applied AI (RAG):** a customer-facing FastAPI assistant answers product and pricing questions using retrieval over a ChromaDB vector store and OpenAI, with guardrails that keep it on-topic.
- **AIOps (also in repo):** an AWS Bedrock agent ("Kira") that diagnoses incidents by calling Lambda tools over live logs, metrics, and cluster health.

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Application | React, Node.js / TypeScript, PostgreSQL |
| AI assistant | Python, FastAPI, ChromaDB (vector store), OpenAI API (embeddings + chat) |
| Containers | Docker, Docker Compose |
| Orchestration | Kubernetes (AWS EKS 1.34) |
| Infrastructure | Terraform (modular: VPC, EKS, ECR, ArgoCD) |
| CI/CD | GitHub Actions (parallel matrix build) |
| Registry | Amazon ECR (8 repositories) |
| GitOps | ArgoCD + Kustomize |
| Observability | Prometheus (kube-prometheus-stack) + Grafana |
| AIOps (optional) | AWS Bedrock Agent (Amazon Nova Lite) + Lambda action groups + Streamlit |

---

## Live on AWS EKS

The platform running on a real EKS cluster: ArgoCD synced and healthy, all pods up
(including `ai-assistant` and `chroma`), and eight image repositories in ECR.

<table>
  <tr>
    <td width="50%"><b>ArgoCD: boutique app Synced &amp; Healthy</b><br><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/argocd_health.png" width="440"></td>
    <td width="50%"><b>ArgoCD: application sync view</b><br><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/argocd_sync.png" width="440"></td>
  </tr>
  <tr>
    <td width="50%"><b>All pods Running on EKS</b><br><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/All_healthly_and_pods.png" width="440"></td>
    <td width="50%"><b>Amazon ECR: 8 image repositories</b><br><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/ECR.png" width="440"></td>
  </tr>
</table>

### Observability

<table>
  <tr>
    <td width="50%"><b>Grafana: live service dashboard</b><br><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/devops-aiops-grafana1.png" width="440"></td>
    <td width="50%"><b>Prometheus: scrape targets UP</b><br><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/devops-aiops-Prometheus.png" width="440"></td>
  </tr>
</table>

---

## Customer-facing AI assistant (RAG)

A standalone **Python + FastAPI** service, independent of the Node.js backend, that
answers shopper questions about **products and pricing**. It embeds a small product +
policy knowledge base into **ChromaDB**, retrieves the most relevant context for each
question, and asks **OpenAI** to answer grounded in that context. A guardrail keeps it
strictly on-topic — it politely refuses anything unrelated to the store. A React chat
widget in the storefront calls it at `/ai/ask` (proxied by nginx to the service).

<table>
  <tr>
    <td width="50%"><b>Storefront (React frontend)</b><br><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/devops-aiops-app.png" width="440"></td>
    <td width="50%"><b>AI assistant answering in the storefront</b><br><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/AI-Chatbot.png" width="440"></td>
  </tr>
</table>

**Behaviours it demonstrates:** answering live pricing, answering company-specific
questions from retrieved docs (e.g. restock policy) that a base model could not know,
and refusing off-topic questions.

---

## AIOps assistant "Kira"

Also included (`projects/aiops-assistant/`): an **AWS Bedrock agent** that reasons like
an SRE. Asked "are any services down?", it decides which of three **Lambda** tools to
call (CloudWatch logs, Prometheus metrics, EKS health), correlates the results, and
returns a root cause plus a fix.

<table>
  <tr>
    <td width="50%"><b>Kira: cluster healthy</b><br><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/devops-aiops-UI.png" width="440"></td>
    <td width="50%"><b>Kira: detecting a service scaled to zero</b><br><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/devops-aiops-UI-3.0.png" width="440"></td>
  </tr>
</table>

---

## How it works (by layer)

**Application.** Seven services (React frontend, API gateway, and `auth`,
`product-service`, `order-service`, `orders`, `user-service`) backed by PostgreSQL
(four databases). The gateway is the single entry point.

**AI assistant.** An eighth service, `ai-assistant` (FastAPI), plus `chroma` (vector DB),
serving the storefront chat widget.

**Build and ship.** A push to `main` triggers GitHub Actions, which builds all eight
images in parallel, pushes them to ECR, and rewrites the image tags in `gitops/`.

**Deliver.** ArgoCD watches `gitops/` and reconciles the cluster to match Git, with
self-heal and drift detection.

**Observe.** Every backend exposes `/metrics`; a `ServiceMonitor` tells Prometheus to
scrape it, and Grafana ships a pre-loaded dashboard.

---

## Deploy it yourself

**Local (Docker Compose):** build the frontend, then `docker compose up -d --build` in
`projects/boutique-microservices/` (set `OPENAI_API_KEY` in `ai-assistant/.env`).

**AWS (EKS + GitOps):**
1. `terraform init && terraform apply` in `projects/Infrastructure/` (VPC, EKS, 8 ECR repos, ArgoCD, monitoring).
2. `aws eks update-kubeconfig --name eks-cluster --region us-east-1`.
3. Run the GitHub Actions pipeline to build + push images and bump manifest tags.
4. `kubectl apply -f gitops/argo-cd.yml -n argocd` and let ArgoCD sync.
5. Set the real OpenAI key in-cluster, then run the DB restore job to seed Postgres.

> Cost: EKS, on-demand nodes, and any LoadBalancer bill hourly. Run `terraform destroy`
> and remove LoadBalancers/PVCs when done.

---

## Repository structure

```
enterprise-cloudops-ai-platform/
├── projects/
│   ├── boutique-microservices/    # App: 7 services + Postgres + ai-assistant (FDE) + chroma
│   ├── Infrastructure/            # Terraform modules for AWS / EKS / ECR / ArgoCD
│   └── aiops-assistant/           # AIOps agent "Kira" (Bedrock + Lambdas + Streamlit)
├── gitops/
│   ├── argo-cd.yml                # ArgoCD Application manifest
│   ├── kustomization.yml          # Kustomize entry point
│   └── k8s/                       # Deployments, Services, StatefulSets, ServiceMonitors
│       └── ai-assistant/          # ai-assistant + chroma manifests
├── Docs/                          # Architecture diagram + screenshots + Project.md
└── .github/workflows/ci.yml       # CI pipeline (build, push, update manifests)
```

A detailed component-by-component walkthrough and interview-prep guide lives in
[`Docs/Project.md`](https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/Project.md).

---

## Troubleshooting and lessons learned

Real problems solved while building and deploying this platform.

| Symptom | Root cause | Fix |
|---------|-----------|-----|
| `terraform apply` -> `Error: Unauthorized` on namespaces | Short-lived EKS auth token expired during the long cluster build | Re-run apply (fresh token), or use an `exec` auth plugin |
| `Error locating chart ... no cached repo found` | Helm provider needs the chart repos in the local cache | `helm repo add` argo + prometheus-community, then `helm repo update` |
| Pods `ImagePullBackOff` on a tag `not found` | Manifests referenced an old placeholder image tag, not the tag CI actually pushed | Rewrote manifests to the real ECR tag and re-synced |
| New pods stuck `Pending` — "Too many pods" | Single `m7i-flex.large` node hit its pod/IP limit during a rolling update | Scaled the node group to 2 nodes |
| Backends `CrashLoopBackOff` — `database "auth_db" does not exist` | Postgres starts empty in Kubernetes (no auto-run init scripts) | Ran the DB restore Job to create and seed the four databases |
| `terraform destroy` -> `DependencyViolation` on subnet/VPC | Kubernetes-created LoadBalancer / ENIs / security groups outlived the cluster | Deleted the leftover ELB, ENIs, and non-default security groups, then re-ran destroy |
| `kubectl scale --replicas=0` instantly reverted | ArgoCD self-heal reconciled drift back to Git | GitOps working as intended; disable auto-sync to test failures |
| Windows / Git Bash path mangling | MSYS auto-converts leading-slash args | `export MSYS_NO_PATHCONV=1`, `pwd -W`, `python` not `python3` |

---

## Acknowledgements

Built by following and adapting DevOps + AI tutorial series, then debugged, extended, and
deployed end-to-end on real AWS infrastructure.