# Project Deep-Dive & Interview Preparation

A detailed walkthrough of the **Enterprise CloudOps AI Platform** — what every piece
does, *why* it's there, the design decisions behind it, the problems solved during
deployment, and the questions you should be ready to answer about it.

> Use this as your study sheet. If you can explain every section below in your own
> words, you can defend this project in an interview.

---

## 1. The 30-second pitch

> "I built and deployed a seven-service e-commerce application to a production-style
> AWS EKS cluster. The infrastructure is fully defined in Terraform, images are built
> and shipped by a GitHub Actions pipeline into ECR, and ArgoCD continuously deploys
> them to Kubernetes using GitOps. The whole system is observable through Prometheus
> and Grafana, with pod logs flowing to CloudWatch. On top of that, I built an AIOps
> assistant on AWS Bedrock — a natural-language agent that diagnoses incidents by
> calling Lambda tools to read live logs, metrics, and cluster health, then returns a
> root-cause analysis."

That single paragraph touches IaC, containers, Kubernetes, CI/CD, GitOps,
observability, and AI — the full modern DevOps surface.

---

## 2. The big picture: how a request flows

**A customer request:**
`Browser → Frontend (nginx serving React) → API Gateway → backend service → PostgreSQL → back up the chain.`

The gateway is the single front door. The browser never talks to `auth` or
`product-service` directly — it always goes through the gateway, which routes by path
(e.g. `/api/auth/*` → auth service). This is the **API Gateway pattern**: one entry
point, centralised routing, and a clean separation between "public edge" and "internal
services."

**A deployment:**
`git push → GitHub Actions builds 7 images → pushes to ECR → updates image tags in gitops/ → ArgoCD sees the change → syncs to EKS → new pods roll out.`

**An AI diagnosis:**
`Engineer asks Kira a question → Bedrock agent decides which tool it needs → invokes a Lambda → Lambda queries CloudWatch / Prometheus / EKS → agent correlates results → returns a plain-English root cause.`

---

## 3. Component by component (what + why)

**Frontend (React + nginx).** A single-page app. In production it's built to static
files and served by nginx. *Why nginx?* Static assets should be served by a web server,
not a Node process — it's faster, smaller, and the standard pattern.

**API Gateway.** Routes external requests to internal services and is the only service
exposed to the edge. *Why?* It decouples clients from the internal topology — services
can move, split, or scale without clients knowing.

**Backend microservices (`auth`, `product-service`, `order-service`, `orders`,
`user-service`).** Each owns one business capability and **its own database**. *Why
separate databases?* It's the database-per-service pattern: services stay loosely
coupled and independently deployable; no service reaches into another's tables.

**PostgreSQL.** A single Postgres instance hosting four logical databases
(`auth_db`, `products_db`, `orders_db`, `users_db`). *Why one instance with four DBs in
this project?* Cost and simplicity for a demo — in real production each service might
get its own managed database (e.g. RDS).

**Terraform.** Defines the VPC, subnets, EKS cluster, managed node group, ECR repos,
IAM roles, and Helm-installed add-ons. *Why IaC?* The whole environment is reproducible,
reviewable, and destroyable with one command — no click-ops, no drift, no "works on my
console."

**ECR.** Private Docker registry. *Why not Docker Hub?* It's inside your AWS account,
integrates with EKS IAM, and avoids public rate limits.

**GitHub Actions.** Builds all seven images in a **parallel matrix job** and pushes them
to ECR, then rewrites the image tags in the GitOps manifests. *Why a matrix?* Seven
services built sequentially is slow; a matrix builds them concurrently.

**ArgoCD.** Watches the `gitops/` directory and reconciles the cluster to match Git.
*Why GitOps?* Git becomes the single source of truth. The cluster's desired state is
versioned, auditable, and self-healing — if someone changes something by hand, ArgoCD
reverts it.

**Prometheus + Grafana.** Prometheus scrapes each service's `/metrics` endpoint (told to
do so by a `ServiceMonitor`); Grafana visualises it. *Why?* You can't operate what you
can't see.

**Fluent Bit → CloudWatch.** A DaemonSet on every node that forwards pod logs to a
CloudWatch log group. *Why?* Centralised, searchable logs that outlive the pods — and
the data source the AIOps agent reads.

**AIOps assistant (Bedrock agent + 3 Lambdas + Streamlit).** The intelligence layer —
covered in detail in section 7.

---

## 4. System design concepts demonstrated

| Concept | Where it shows up here |
|---------|------------------------|
| Microservices & bounded contexts | Seven services, each owning one capability + its own DB |
| API Gateway | Single edge entry point routing to internal services |
| Statelessness & horizontal scaling | Services hold no local state; replicas can scale out |
| Infrastructure as Code | Terraform provisions everything |
| Immutable infrastructure | Each deploy is a new image tagged by commit SHA |
| GitOps / declarative delivery | ArgoCD reconciles cluster to Git |
| Observability (3 pillars) | Metrics (Prometheus), logs (CloudWatch), and health (EKS API) |
| Separation of concerns | Build (CI) vs deploy (CD/GitOps) are decoupled |
| Event-driven / tool-calling AI | Bedrock agent invokes Lambdas on demand |

---

## 5. The delivery pipeline (CI ≠ CD)

A common interview trap is conflating CI and CD. Here they're cleanly separated:

- **CI (GitHub Actions):** on push, build + test + push images to ECR, then bump the
  image tags in `gitops/k8s/`. CI's job ends at the registry and the Git commit.
- **CD (ArgoCD):** independently, ArgoCD notices the manifest change in Git and applies
  it to the cluster. CD's job is reconciliation.

**Why decouple them?** The pipeline that builds artifacts shouldn't also have cluster
credentials. With GitOps, nothing pushes *to* the cluster — the cluster *pulls* its
desired state from Git. That's more secure and gives you a full audit trail and easy
rollback (revert the commit).

---

## 6. Observability: the three questions

Good observability answers three questions, and this project has a source for each:

1. **Is it up?** — EKS cluster status + deployment replica counts (desired vs available).
2. **How fast / how loaded?** — Prometheus metrics: request rate, latency, CPU, memory.
3. **What broke?** — CloudWatch logs (errors, stack traces, restart loops).

Grafana's dashboard surfaces #1 and #2; CloudWatch holds #3. The AIOps agent is
powerful precisely because it can pull from **all three** and correlate them — something
a single dashboard can't do on its own.

---

## 7. AIOps internals (the part that makes this stand out)

This is the differentiator, so understand it deeply.

**Foundation model.** The agent runs on **Amazon Nova Lite** via Bedrock. It's the
reasoning engine — it interprets the question and decides what to do. (Nova Lite was
chosen for cost; a stronger model like Nova Pro or Claude reasons and re-invokes tools
more reliably — a real tradeoff, see section 8.)

**The agent.** A Bedrock Agent is the model **plus** instructions (a persona — here, an
SRE) **plus** a set of tools it's allowed to call. It orchestrates multi-step reasoning.

**Tool calling / action groups.** The agent can't query AWS by itself — it calls
**action groups**, each backed by a **Lambda function** with a defined input/output
schema:
- `fetch_logs` → reads recent error logs from CloudWatch.
- `fetch_metrics` → queries Prometheus (CPU, memory, request/error rates).
- `fetch_health` → checks EKS cluster status and per-deployment replica health.

**The flow.** You ask *"Are any services down?"* → the model reasons that it needs
health data → it emits a tool-call for `fetch_health` → Bedrock invokes that Lambda →
the Lambda queries Prometheus + the EKS API and returns structured JSON → the model
reads that JSON, sees `orders` has 0/0 replicas, and replies in plain English: *"orders
is scaled to zero — here's the likely cause and the fix."*

**Why this design?** It's the same pattern as modern AI agents everywhere: the LLM
*decides* and *explains*; deterministic code (Lambdas) *fetches* the real data. The model
never guesses at live state — it always grounds its answer in a tool result.

**Key talking point:** during testing, the agent once answered "all healthy" right after
a service was scaled down. The cause wasn't a broken tool — the smaller model reused its
*previous* tool result instead of re-fetching. The fix was to force a fresh tool call.
That's a real, nuanced AIOps lesson about model capability vs. tooling correctness.

---

## 8. Key design decisions & tradeoffs

**Why EKS instead of ECS or plain EC2?** Kubernetes is the industry standard for
portable orchestration and is what most "DevOps engineer" roles expect. The cost is
complexity — EKS has a steeper learning curve than ECS.

**Why microservices for a demo?** To exercise the patterns (gateway, per-service DBs,
independent deploys, service-to-service metrics). A monolith wouldn't show them. The
tradeoff is operational overhead — seven services to build, ship, and watch.

**Why Nova Lite for the agent?** Cost. It's cheap enough to run a demo freely. The
tradeoff is weaker agentic behaviour (it sometimes reuses cached tool output rather than
re-invoking). A production system would weigh cost against a stronger model.

**Why a single-node cluster?** Cost again — one `m7i-flex.large`. The tradeoff is slow,
serial pod rollouts and pod/IP limits; production would run multiple right-sized nodes.

**Why GitOps over `kubectl apply` in CI?** Security and auditability — the cluster pulls
from Git rather than CI pushing into it.

---

## 9. Troubleshooting deep-dive (issue → cause → fix → lesson)

These are gold in interviews — they prove you can operate, not just deploy.

**1. `terraform apply` failed with `Error: Unauthorized`.**
*Cause:* the Kubernetes/Helm Terraform providers authenticated with a short-lived EKS
token that expired during the long cluster build. *Fix:* re-run apply (fresh token), or
configure the provider to use an `exec` plugin that fetches a token on demand. *Lesson:*
understand how provider auth and token lifetimes interact in long applies.

**2. Pods stuck in `InvalidImageName`.**
*Cause:* manifests still had the literal `<AWS_ACCOUNT_ID>` placeholder. *Fix:*
substitute the real account ID and push images first. *Lesson:* a pod can't pull an
image that doesn't exist yet, and placeholders must be rendered.

**3. `auth`/`orders` crash-looping with a database error.**
*Cause:* in Kubernetes, Postgres starts with an empty data directory — unlike Docker
Compose, the init scripts don't auto-run. *Fix:* run a database restore Job to create
and seed the four databases. *Lesson:* local-vs-cluster behaviour differs; never assume
parity.

**4. Fluent Bit couldn't authenticate to CloudWatch (`NoCredentialProviders`).**
*Cause:* the node's IMDS hop limit was 1, so pods couldn't reach instance metadata for
credentials. *Fix:* raise the hop limit to 2. *Lesson:* know how pods get AWS
credentials and how IMDSv2 hop limits gate that.

**5. Bedrock agent said "all healthy" after a service was scaled to zero.**
*Cause:* the model reused its earlier tool result instead of re-fetching. *Fix:* force a
fresh tool call (new session / explicit re-check). *Lesson:* agentic reliability depends
on model capability, not just correct tools.

**6. A manual `kubectl scale --replicas=0` instantly bounced back to 1.**
*Cause:* ArgoCD self-heal detected the drift and reverted it to the Git-declared state.
*Fix:* this is GitOps working correctly — to demonstrate a failure you disable auto-sync
first. *Lesson:* in a GitOps system, the cluster is not the source of truth; Git is.

**7. Windows/Git Bash path and command issues.**
*Cause:* MSYS auto-converts leading-slash arguments and ships `python3` differently.
*Fix:* `MSYS_NO_PATHCONV=1`, `pwd -W`, and `python` instead of `python3`. *Lesson:*
tooling environment matters; the same script behaves differently across shells.

---

## 10. Likely interview questions

**"Walk me through what happens when you push code."**
Push → GitHub Actions builds and pushes seven images to ECR in parallel → it updates the
image tags in the GitOps repo → ArgoCD detects the change and syncs the cluster → new
pods roll out. CI builds; ArgoCD deploys; they're decoupled.

**"What's the difference between CI and CD here?"**
CI (GitHub Actions) produces artifacts and ends at ECR + a Git commit. CD (ArgoCD) pulls
desired state from Git into the cluster. Nothing pushes into the cluster — it pulls.

**"How does the cluster pull images securely?"**
The node's IAM role has ECR pull permissions; EKS authenticates to ECR with that role —
no static registry credentials.

**"What is GitOps and why use it?"**
Declarative delivery where Git is the single source of truth and an in-cluster
controller (ArgoCD) continuously reconciles reality to Git. Benefits: audit trail, easy
rollback (revert a commit), drift detection, and no external system holding cluster
credentials.

**"How would you know if a service is down?"**
Three signals: Prometheus alerts on metrics, CloudWatch on error logs, and the deployment
replica count (desired vs available). In this project the AIOps agent correlates all
three.

**"Explain the AI part — is it just a chatbot?"**
No. It's an agent with tools. The model decides which Lambda to call; the Lambda fetches
real data from CloudWatch/Prometheus/EKS; the model grounds its answer in that data. It
reasons and explains; deterministic code fetches.

**"What would you do differently in production?"**
Multi-node, right-sized cluster with autoscaling; managed databases per service; secrets
in a manager (not env files); a stronger agent model; alerting + on-call integration;
and remote, locked Terraform state.

**"What was the hardest bug?"**
Pick one from section 9 and tell the story: symptom → how you isolated the cause → the
fix → the lesson. The IMDS hop-limit or the GitOps self-heal revert are great ones
because they show real Kubernetes/AWS depth.

---

## 11. If I rebuilt it (production-readiness gaps)

Being able to critique your own project signals maturity:

- **State & secrets:** remote Terraform state with locking; secrets in AWS Secrets
  Manager or External Secrets, not `.env` files.
- **Resilience:** multiple nodes + cluster autoscaler; resource requests/limits on every
  pod; PodDisruptionBudgets.
- **Data:** managed RDS per service instead of one in-cluster Postgres.
- **Delivery:** progressive delivery (canary/blue-green) via Argo Rollouts.
- **Observability:** alerting rules + a paging integration; distributed tracing.
- **AIOps:** a stronger model, plus guardrails so the agent can *suggest* but not
  *execute* remediations without approval.

---

*Tip: keep this file in `docs/`. It doubles as project documentation for anyone reading
the repo and as your personal interview prep.*