# Project Deep-Dive & Interview Preparation

A detailed walkthrough of the **Enterprise CloudOps AI Platform** — what every piece
does, why it is there, the design decisions behind it, the problems solved during
deployment, and the questions you should be ready to answer.

> Use this as your study sheet. If you can explain every section below in your own
> words, you can defend this project in an interview.

<p align="center">
  <img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/AI_Archtecture.png" alt="Architecture" width="900">
</p>

---

## 1. The 30-second pitch

> "I built and deployed an eight-service application to a production-style AWS EKS
> cluster. Infrastructure is defined in Terraform; images are built by a GitHub Actions
> pipeline and pushed to ECR; ArgoCD continuously deploys them to Kubernetes via GitOps
> with self-healing and drift detection. The stack is observable through Prometheus and
> Grafana. The eighth service is a customer-facing AI shopping assistant — a FastAPI RAG
> service that answers product and pricing questions using a ChromaDB vector store and
> OpenAI, with guardrails. I also built an AIOps agent on AWS Bedrock that diagnoses
> incidents from live logs, metrics, and cluster health."

That single paragraph touches IaC, containers, Kubernetes, CI/CD, GitOps, observability,
applied GenAI (RAG), and AIOps — the full modern DevOps + AI surface.

---

## 2. The big picture: how a request flows

**A customer request:**
`Browser -> Frontend (nginx serving React) -> API Gateway -> backend service -> PostgreSQL -> back up the chain.`
The gateway is the single front door (API Gateway pattern): one entry point, centralised
routing, clean separation of public edge from internal services.

**An AI chat request:**
`Browser widget -> /ai/ask (nginx proxy) -> ai-assistant (FastAPI) -> ChromaDB (retrieve context) + OpenAI (generate answer) -> reply.`

**A deployment:**
`git push -> GitHub Actions builds 8 images -> pushes to ECR -> updates image tags in gitops/ -> ArgoCD syncs -> new pods roll out.`

---

## 3. Component by component (what + why)

**Frontend (React + nginx).** SPA built to static files, served by nginx, which also
proxies `/api/` to the gateway and `/ai/` to the assistant.

**API Gateway.** Routes external requests to internal services; the only edge-facing app
service. Decouples clients from internal topology.

**Backend microservices (auth, product-service, order-service, orders, user-service).**
Each owns one capability and its own database (database-per-service pattern).

**PostgreSQL.** One instance, four logical databases (auth/products/orders/users). In
Kubernetes it starts empty, so a restore Job seeds it.

**ai-assistant (FastAPI) — the FDE service.** A separate Python service that answers
product/pricing questions with RAG. Independent of the Node.js backend; talks to the
frontend over HTTP. See section 7.

**ChromaDB.** Vector store holding embeddings of the product + policy knowledge base.

**Terraform.** Defines VPC, subnets, EKS, node group, ECR (8 repos), IAM/OIDC, EBS CSI
add-on, and the ArgoCD + monitoring Helm releases. Reproducible, reviewable, destroyable.

**ECR.** Private registry, one repo per service (8 total, including `ai-assistant`).

**GitHub Actions.** Parallel matrix build of 8 images -> ECR, then bumps the GitOps tags.

**ArgoCD.** Watches `gitops/`, reconciles the cluster to Git; self-healing + drift
detection.

**Prometheus + Grafana.** Prometheus scrapes each service's `/metrics` (via
ServiceMonitor); Grafana visualises. The assistant also exposes `/metrics`.

**AIOps agent "Kira" (Bedrock + Lambdas).** Separate, internal SRE assistant — section 8.

---

## 4. System design concepts demonstrated

| Concept | Where it shows up |
|---------|-------------------|
| Microservices & bounded contexts | 7 services, each owning one capability + its own DB |
| API Gateway | Single edge entry point |
| Retrieval-Augmented Generation | ai-assistant grounds LLM answers in ChromaDB retrieval |
| Guardrails for LLM apps | System prompt restricts scope; off-topic questions refused |
| Infrastructure as Code | Terraform provisions everything |
| Immutable infrastructure | Each deploy is a new image tagged by commit SHA |
| GitOps / declarative delivery | ArgoCD reconciles cluster to Git |
| Observability | Metrics (Prometheus/Grafana) + health (EKS API) |
| Separation of concerns | Build (CI) vs deploy (CD/GitOps) decoupled |

---

## 5. The delivery pipeline (CI is not CD)

- **CI (GitHub Actions):** on push/dispatch, build + push 8 images to ECR, then bump image
  tags in `gitops/`. CI ends at the registry and a Git commit.
- **CD (ArgoCD):** independently notices the Git change and applies it to the cluster.

Why decouple: the build pipeline never holds cluster credentials — the cluster *pulls* its
desired state from Git. More secure, fully audited, trivial rollback (revert a commit).

---

## 6. Observability: the three questions

1. **Is it up?** EKS cluster + deployment replica counts.
2. **How fast / how loaded?** Prometheus metrics (request rate, latency, CPU, memory).
3. **What broke?** Logs (and, in the AIOps setup, CloudWatch).

Grafana surfaces #1 and #2; the AIOps agent can correlate all three.

---

## 7. The FDE AI assistant (RAG internals)

**Goal:** a customer-facing assistant that answers only product + pricing questions,
grounded in real data.

**Pipeline per question:**
1. **Embed** the question with OpenAI `text-embedding-3-small`.
2. **Retrieve** the top-k most similar chunks from **ChromaDB** (products + policy docs).
3. **Generate** an answer with an OpenAI chat model, given the retrieved context and a
   strict system prompt.
4. **Guardrail:** if the question is off-topic or the answer is not in context, it refuses.

**Why this design:** the LLM *reasons and explains*; deterministic retrieval supplies the
*facts*. The model never invents prices — it answers from retrieved context, so answers
stay correct and current. Embeddings are computed with OpenAI and passed to Chroma
explicitly, so the Chroma container needs no embedding model of its own.

**Talking point:** it answers company-specific questions (e.g. "when will X be back in
stock?") from an internal policy document — something a base model could not know —
which is the whole point of RAG.

---

## 8. AIOps agent "Kira" (Bedrock tool-calling)

A separate, internal agent (`projects/aiops-assistant/`). A **Bedrock agent** (Amazon Nova
Lite) with an SRE persona and three **Lambda** action groups: `fetch_logs` (CloudWatch),
`fetch_metrics` (Prometheus), `fetch_service_health` (EKS). Asked a question, the model
decides which tool to call; the Lambda fetches real data; the model correlates and returns
a root cause. Same tool-calling pattern as the FDE assistant, but pointed at *infra*
instead of *products*.

---

## 9. Deploying to EKS via GitOps (walkthrough)

1. `terraform apply` builds VPC, EKS, node group, 8 ECR repos, and Helm-installed ArgoCD +
   monitoring. (If it fails on namespaces with `Unauthorized`, the EKS token expired
   mid-apply — re-run.)
2. `aws eks update-kubeconfig` to connect `kubectl`.
3. Run the CI pipeline to build + push all 8 images and bump the GitOps tags.
4. `kubectl apply -f gitops/argo-cd.yml` registers the app; ArgoCD syncs the platform.
5. Patch the real `OPENAI_API_KEY` into the cluster secret; run the DB restore Job.
6. Verify: `kubectl get applications -n argocd` -> `Synced / Healthy`; all pods Running.

---

## 10. Key design decisions & tradeoffs

- **EKS over ECS/plain EC2:** industry-standard Kubernetes; cost is complexity.
- **Microservices for a demo:** exercises gateway, per-service DBs, independent deploys;
  cost is operational overhead.
- **RAG assistant as a separate service:** language-agnostic, independently scalable and
  deployable; the FDE pattern.
- **OpenAI embeddings passed into Chroma:** simpler, lighter Chroma container.
- **GitOps over `kubectl apply` in CI:** security and auditability.
- **Single small node (then scaled to 2):** cost first; scaled out when pod capacity was hit.

---

## 11. Troubleshooting deep-dive (issue -> cause -> fix -> lesson)

**1. `terraform apply` -> `Unauthorized` on namespaces.** Short-lived EKS token expired
during the long build. *Fix:* re-run (fresh token). *Lesson:* provider auth vs token
lifetime on long applies.

**2. `Error locating chart ... no cached repo found`.** The Helm provider reads the local
repo cache, which was empty. *Fix:* `helm repo add` argo + prometheus-community, then
`helm repo update`. *Lesson:* the Helm provider does not fetch indexes for you.

**3. Pods `ImagePullBackOff`: tag not found.** Manifests still referenced an old placeholder
image tag; CI had pushed under the commit SHA. *Fix:* rewrite manifests to the real tag,
re-sync. *Lesson:* the deployed tag must exist in the registry — placeholders bite.

**4. New pods `Pending`: "Too many pods".** A single `m7i-flex.large` hit its pod/IP limit,
worsened by old+new pods coexisting during a rolling update. *Fix:* scale the node group to
2. *Lesson:* node instance type caps max pods; rollouts need headroom.

**5. Backends `CrashLoopBackOff`: `database "auth_db" does not exist` (3D000).** Postgres
starts empty in Kubernetes. *Fix:* run the DB restore Job, then restart the services.
*Lesson:* local (Compose auto-init) vs cluster behaviour differs.

**6. `kubectl scale --replicas=0` instantly reverted.** ArgoCD self-heal reconciled the
drift. *Fix:* expected behaviour; disable auto-sync to test failures. *Lesson:* in GitOps,
Git is the source of truth, not the cluster.

**7. Windows/Git Bash issues.** MSYS path mangling and `python3` vs `python`. *Fix:*
`MSYS_NO_PATHCONV=1`, `pwd -W`, `python`. *Lesson:* tooling environment matters.

---

## 12. Likely interview questions

**"Walk me through a deployment."** Push -> GitHub Actions builds/pushes 8 images to ECR ->
bumps GitOps tags -> ArgoCD syncs -> pods roll out. CI builds; ArgoCD deploys; decoupled.

**"What is RAG and why use it?"** Retrieval-Augmented Generation: retrieve relevant context
from a vector store and give it to the LLM so answers are grounded in real, current data
rather than the model's memory. Here it keeps product/price answers accurate and lets the
assistant answer company-specific questions.

**"How do you keep the assistant from going off the rails?"** A strict system prompt scopes
it to products/pricing and refuses otherwise; answers are grounded in retrieved context; a
refusal counter is exposed in `/metrics`.

**"CI vs CD here?"** CI (Actions) ends at ECR + a Git commit; CD (ArgoCD) pulls desired
state from Git into the cluster. Nothing pushes into the cluster.

**"Hardest bug?"** Pick one from section 11 — the image-tag mismatch or the pod-capacity
`Pending` are great: symptom -> how you isolated it -> fix -> lesson.

**"What would you do in production?"** Remote/locked Terraform state; secrets in a manager
(not `.env`); multi-node autoscaling with resource requests/limits; managed DBs; progressive
delivery; alerting + tracing; the assistant behind auth + rate limits.

---

## 13. If I rebuilt it

- Remote Terraform state + locking; secrets in AWS Secrets Manager / External Secrets.
- Multi-node cluster + autoscaler; resource requests/limits; PodDisruptionBudgets.
- Managed RDS per service instead of one in-cluster Postgres.
- Progressive delivery (canary/blue-green) via Argo Rollouts.
- Alerting rules + paging; distributed tracing.
- Assistant: response caching, eval suite for guardrails, rate limiting, and auth.

---

*Keep this file in `Docs/`. It doubles as project documentation and your interview prep.*