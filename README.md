# Enterprise CloudOps AI Platform

An end-to-end **DevOps + AI** platform on **AWS EKS**: a seven-service e-commerce
microservices application plus a **customer-facing AI shopping assistant**, provisioned
with **Terraform**, delivered through a **GitHub Actions** CI pipeline and **ArgoCD**
GitOps, and observed with **Prometheus + Grafana**. The AI assistant is a
Retrieval-Augmented-Generation (RAG) service built with **FastAPI + ChromaDB + OpenAI**,
and the platform ships with an **eval harness** that measures both the RAG assistant and
the AIOps agent.

<p align="center">
  <img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/Architecture_new.png" alt="Enterprise CloudOps AI Platform architecture" width="960">
</p>

This repository takes an application from a local Docker Compose setup all the way to a
self-healing, observable, AI-assisted platform running live on Kubernetes — and then
**measures** the AI with a reusable evaluation harness.

---

## What this project demonstrates

- **Infrastructure as Code:** entire AWS footprint (VPC, EKS, node groups, ECR, IAM, add-ons) defined in modular Terraform.
- **Container orchestration:** eight microservices packaged as Docker images and run on a managed Kubernetes (EKS) cluster.
- **CI/CD:** GitHub Actions builds and pushes eight service images to ECR in parallel and updates the deployment manifests.
- **GitOps:** ArgoCD continuously reconciles the cluster to the Git-declared state (self-healing, drift detection).
- **Observability:** every service exposes `/metrics`; Prometheus scrapes them and Grafana visualises them.
- **Applied AI (RAG):** a customer-facing FastAPI assistant answers product and pricing questions using retrieval over a ChromaDB vector store and OpenAI, with guardrails that keep it on-topic.
- **AI evaluation:** a reusable harness scores the RAG assistant (refusal accuracy, retrieval precision, faithfulness) and the AIOps agent (tool-selection, diagnosis), plus an OpenAI-vs-Anthropic comparison.
- **Agentic AIOps:** an incident-diagnosis agent ("Kira") built as a **LangGraph** state machine that classifies an alert, selects a tool, correlates results, and produces a root cause — with a visible reasoning trace and Slack notification.

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Application | React, Node.js / TypeScript, PostgreSQL |
| AI assistant | Python, FastAPI, ChromaDB (vector store), OpenAI + Anthropic (chat), OpenAI (embeddings) |
| AIOps agent | LangGraph, OpenAI, Slack (Block Kit), AWS Bedrock (optional live path) |
| Containers | Docker, Docker Compose |
| Orchestration | Kubernetes (AWS EKS 1.34) |
| Infrastructure | Terraform (modular: VPC, EKS, ECR, ArgoCD) |
| CI/CD | GitHub Actions (parallel matrix build) |
| Registry | Amazon ECR (8 repositories) |
| GitOps | ArgoCD + Kustomize |
| Observability | Prometheus (kube-prometheus-stack) + Grafana |

---

## Live on AWS EKS

The platform running on a real EKS cluster: ArgoCD synced and healthy, all pods up
(including `ai-assistant` and `chroma`), and eight image repositories in ECR.

<table>
  <tr>
    <td width="50%"><b>All pods Running + ArgoCD Synced/Healthy</b><br><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/agrocd-pod_health.png" width="440"></td>
    <td width="50%"><b>ArgoCD: application sync view</b><br><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/argocd_sync.png" width="440"></td>
  </tr>
  <tr>
    <td width="50%"><b>Amazon ECR: 8 image repositories</b><br><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/ECR.png" width="440"></td>
    <td width="50%"><b>Storefront (React frontend)</b><br><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/devops-aiops-app.png" width="440"></td>
  </tr>
</table>

---

## Customer-facing AI assistant (RAG)

A standalone **Python + FastAPI** service, independent of the Node.js backend, that
answers shopper questions about **products and pricing**. It embeds a small product +
policy knowledge base into **ChromaDB**, retrieves the most relevant context for each
question, and asks the LLM to answer grounded in that context. A guardrail keeps it
strictly on-topic — it politely refuses anything unrelated to the store.

<table>
  <tr>
    <td width="50%"><b>Storefront chat widget</b><br><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/AI-Chatbot.png" width="440"></td>
    <td width="50%"><b>Grafana: live service dashboard</b><br><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/devops-aiops-grafana1.png" width="440"></td>
  </tr>
</table>

---

## Measuring the AI: evaluation harness

A reusable harness (`projects/boutique-microservices/eval/`) runs fixed test suites
against the assistant and the agent, so quality is a **measured number**, not a claim.
The faithfulness judge is a stronger model held constant across runs, and a sample of its
scores was hand-verified.

**RAG assistant** — 26 cases across in-scope / off-topic / ambiguous buckets:

<p align="center"><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/RAG_Eval.png" width="620"></p>

| Metric | Score |
|--------|-------|
| Refusal accuracy | 0.955 |
| Retrieval precision@k | 1.0 |
| Avg faithfulness (1–5, LLM-judge) | 5.0 |

> The single miss (case `r11`, a return-policy question) is an honest finding: the
> guardrail over-refused a question it should have answered — a concrete v1 → v2 target.

**AIOps agent (Kira)** — 16 offline scenarios against mocked tool outputs:

<p align="center"><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/KIRA_Eval.png" width="620"></p>

| Metric | Score |
|--------|-------|
| Tool-selection accuracy | 0.938 |
| Diagnosis-category accuracy | 0.938 |

**OpenAI vs Anthropic** — the same RAG eval run against both providers (judge held
constant for a fair comparison):

<p align="center"><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/Eval_compare_Api.png" width="720"></p>

| Metric | OpenAI (gpt-4o-mini) | Anthropic (claude-haiku-4-5) |
|--------|----------------------|------------------------------|
| Refusal accuracy | 0.955 | 1.0 |
| Retrieval precision@k | 1.0 | 1.0 |
| Avg faithfulness (1–5) | 5.0 | 5.0 |
| Avg latency (s) | 1.46 | 2.02 |
| Est. cost (USD / run) | 0.00148 | 0.01791 |

> Takeaway: Anthropic edged refusal accuracy but cost ~12× more and ran slower on this
> workload — a real cost/quality/latency trade-off. (Costs use an illustrative price table.)

---

## Agentic AIOps: "Kira" (LangGraph)

Kira diagnoses incidents as a **LangGraph state machine**:
`classify_intent → select_tool → call_tool → correlate → generate_diagnosis`, looping
back to gather more evidence when confidence is low. It calls three tools (`fetch_logs`,
`fetch_metrics`, `fetch_service_health`) — mocked for a laptop-only demo, or live against
CloudWatch/Prometheus/EKS. Every run exposes its full decision trace, and a diagnosis can
be pushed to Slack.

<table>
  <tr>
    <td width="50%"><b>Reasoning trace ("show reasoning steps")</b><br><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/KIRA-LangGraph__local__mock_.png" width="440"></td>
    <td width="50%"><b>Diagnosis + Slack notify</b><br><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/KIRA-LangGraph__local__mock_2_0.png" width="440"></td>
  </tr>
</table>

<p align="center"><img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/graph_kira.png" width="820"></p>

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

**Measure.** The eval harness scores the assistant and the agent and writes JSON results
under `eval/results/`.

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

**Evaluate:** in `projects/boutique-microservices/`, `pip install -r eval/requirements.txt`,
then `python eval/run_rag_eval.py` and `python eval/run_kira_eval.py`.

> Cost: EKS, on-demand nodes, and any LoadBalancer bill hourly. Run `terraform destroy`
> and remove LoadBalancers/PVCs when done.

---

## Repository structure

```
enterprise-cloudops-ai-platform/
├── projects/
│   ├── boutique-microservices/    # App: 7 services + Postgres + ai-assistant + chroma + eval/
│   ├── Infrastructure/            # Terraform modules for AWS / EKS / ECR / ArgoCD
│   └── aiops-assistant/           # Kira: LangGraph graph/, Lambdas, Slack notifier, Streamlit
├── gitops/
│   ├── argo-cd.yml                # ArgoCD Application manifest
│   ├── kustomization.yml          # Kustomize entry point
│   └── k8s/                       # Deployments, Services, StatefulSets, ServiceMonitors
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
| Pods `ImagePullBackOff` on a tag `not found` | Per-service manifests hardcoded an old image tag, not the tag CI pushed | Aligned manifests to the real ECR tag and re-synced |
| New pods stuck `Pending` — "Too many pods" | Single `m7i-flex.large` node hit its pod/IP limit during a rolling update | Scaled the node group to 2 nodes |
| Backends `CrashLoopBackOff` — `database "auth_db" does not exist` | Postgres starts empty in Kubernetes (no auto-run init scripts) | Ran the DB restore Job to create and seed the four databases |
| `ai-assistant` 401 with placeholder key after patching | ArgoCD self-heal reverted the secret to the Git-committed placeholder | Disabled auto-sync, patched the real key, restarted; long-term: External Secrets |
| `terraform destroy` -> `DependencyViolation` on subnet/VPC | Kubernetes-created LoadBalancer / ENIs / security groups outlived the cluster | Deleted the leftover ELB, ENIs, and non-default security groups, then re-ran destroy |
| Windows / Git Bash path mangling | MSYS auto-converts leading-slash args | `export MSYS_NO_PATHCONV=1`, `pwd -W`, `python` not `python3` |

---

## Acknowledgements

Built by following and adapting DevOps + AI tutorial series, then debugged, extended,
measured, and deployed end-to-end on real AWS infrastructure.