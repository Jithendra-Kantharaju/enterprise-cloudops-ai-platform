# Project Deep-Dive & Interview Preparation

A detailed walkthrough of the **Enterprise CloudOps AI Platform** — what every piece
does, why it is there, the design decisions behind it, the problems solved during
deployment, how the AI is measured, and the questions you should be ready to answer.

> Use this as your study sheet. If you can explain every section below in your own
> words, you can defend this project in an interview.

<p align="center">
  <img src="https://raw.githubusercontent.com/Jithendra-Kantharaju/enterprise-cloudops-ai-platform/main/Docs/Architecture_new.png" alt="Architecture" width="900">
</p>

---

## 1. The 30-second pitch

> "I built and deployed an eight-service application to a production-style AWS EKS
> cluster. Infrastructure is Terraform; images are built by GitHub Actions and pushed to
> ECR; ArgoCD deploys them via GitOps with self-healing. It's observable with Prometheus
> and Grafana. The eighth service is a customer-facing RAG assistant (FastAPI + ChromaDB
> + OpenAI) with guardrails — and I measured it with an eval harness: 0.955 refusal
> accuracy, 1.0 retrieval precision, 5.0 faithfulness over 26 cases, plus an
> OpenAI-vs-Anthropic comparison. I also built an AIOps agent, 'Kira,' as a LangGraph
> state machine that diagnoses incidents and posts to Slack, scoring 0.938 on tool
> selection and diagnosis."

That paragraph touches IaC, containers, Kubernetes, CI/CD, GitOps, observability, applied
GenAI (RAG), **AI evaluation**, and **agentic AIOps** — the full modern surface, with numbers.

---

## 2. The big picture: how a request flows

**A customer request:**
`Browser -> Frontend (nginx serving React) -> API Gateway -> backend service -> PostgreSQL -> back up the chain.`

**An AI chat request:**
`Browser widget -> /ai/ask (nginx proxy) -> ai-assistant (FastAPI) -> ChromaDB (retrieve context) + LLM (generate answer) -> reply.`

**A deployment:**
`git push -> GitHub Actions builds 8 images -> pushes to ECR -> updates image tags in gitops/ -> ArgoCD syncs -> new pods roll out.`

**An incident diagnosis (Kira):**
`alert -> classify_intent -> select_tool -> call_tool -> correlate -> (loop if low confidence) -> generate_diagnosis -> Slack.`

---

## 3. Component by component (what + why)

**Frontend (React + nginx).** SPA served by nginx, which proxies `/api/` to the gateway
and `/ai/` to the assistant.

**API Gateway.** The single edge-facing app service; decouples clients from internal topology.

**Backend microservices (auth, product-service, order-service, orders, user-service).**
Each owns one capability and its own database.

**PostgreSQL.** One instance, four logical databases (auth/products/orders/users); seeded
by a restore Job because Postgres starts empty in Kubernetes.

**ai-assistant (FastAPI).** A separate Python service answering product/pricing questions
with RAG; provider-agnostic (OpenAI or Anthropic via `llm_provider.py`). See §7.

**ChromaDB.** Vector store of the product + policy embeddings; runs as a pod in the cluster.

**Terraform.** VPC, subnets, EKS, node group, ECR (8 repos), IAM/OIDC, EBS CSI, and the
ArgoCD + monitoring Helm releases.

**ECR / GitHub Actions / ArgoCD / Prometheus + Grafana.** Registry; parallel image build +
tag bump; GitOps reconciliation; metrics + dashboards.

**Kira (LangGraph agent).** Internal AIOps agent — see §8.

**Eval harness.** Reusable scorers for the assistant and the agent — see §9.

---

## 4. System design concepts demonstrated

| Concept | Where it shows up |
|---------|-------------------|
| Microservices & bounded contexts | 7 services, each owning one capability + its own DB |
| API Gateway | Single edge entry point |
| Retrieval-Augmented Generation | ai-assistant grounds LLM answers in ChromaDB retrieval |
| Guardrails for LLM apps | System prompt restricts scope; off-topic questions refused |
| Agentic reasoning | Kira as a LangGraph state machine with a confidence loop |
| AI evaluation | Refusal / retrieval / faithfulness + tool-selection / diagnosis scoring |
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

Grafana surfaces #1 and #2; Kira correlates all three.

---

## 7. The RAG assistant (internals)

**Pipeline per question:** (1) embed the question with OpenAI `text-embedding-3-small`;
(2) retrieve the top-k most similar chunks from ChromaDB; (3) generate an answer with the
chat model, given the retrieved context and a strict system prompt; (4) guardrail — if
off-topic or unsupported by context, refuse.

**Why this design:** the LLM *reasons and explains*; deterministic retrieval supplies the
*facts*, so the model never invents prices. Embeddings are computed with OpenAI and passed
to Chroma explicitly, so the Chroma container needs no embedding model of its own.

**Provider-agnostic:** `llm_provider.py` exposes one `generate()` interface implemented for
both OpenAI and Anthropic, switched by `LLM_PROVIDER`. Embeddings stay on OpenAI in both
cases, so only the *generation* model varies — which is what makes the comparison fair.

---

## 8. Kira: agentic AIOps as a LangGraph state machine

Kira's decision logic is a **LangGraph** `StateGraph`:
`classify_intent → select_tool → call_tool → correlate → generate_diagnosis`, with a
conditional edge that loops back to `select_tool` when confidence is below threshold
(capped at 3 loops). It calls three tools — `fetch_logs` (CloudWatch), `fetch_metrics`
(Prometheus), `fetch_service_health` (EKS) — through a **mock/live switch**: mock returns
canned fixtures for a zero-AWS laptop demo; live calls the real Lambdas.

The graph keeps a **trace** of every node, surfaced in the Streamlit UI as a "show
reasoning steps" expander — the best live interview demo, because you can walk the decision
path out loud. A generated diagnosis can be pushed to Slack via a Block Kit message.

*(An earlier version used a Bedrock agent for tool-calling; the LangGraph refactor makes
the reasoning explicit, testable offline, and provider-independent.)*

---

## 9. Measuring the AI (evaluation methodology)

Quality is a measured number, not a claim. The harness lives in
`projects/boutique-microservices/eval/`.

**RAG eval (26 cases).** Buckets: clearly in-scope, clearly off-topic, ambiguous. Scores:
- **Refusal accuracy** — did it refuse off-topic and answer in-scope? **0.955**
- **Retrieval precision@k** — was the expected source doc in the retrieved chunks? **1.0**
- **Faithfulness (1–5)** — LLM-judge (a *stronger* model, held constant) rates how grounded
  each answer is in the retrieved context. **5.0**, with ~8 scores hand-verified so the
  judge isn't rubber-stamping.
- **Honest finding:** case `r11` (return policy) over-refused — a real v1 → v2 target.

**Kira eval (16 offline scenarios).** Mocked tool outputs; scores **tool-selection accuracy
0.938** and **diagnosis-category accuracy 0.938**. Two misses (`k03` crash-loop tool,
`k15` diagnosis) are the kind of debatable edge cases that make the number credible.

**Provider comparison.** The same RAG eval run against OpenAI (`gpt-4o-mini`) and Anthropic
(`claude-haiku-4-5`), judge held constant:

| Metric | OpenAI | Anthropic |
|--------|--------|-----------|
| Refusal accuracy | 0.955 | 1.0 |
| Retrieval precision@k | 1.0 | 1.0 |
| Avg faithfulness (1–5) | 5.0 | 5.0 |
| Avg latency (s) | 1.46 | 2.02 |
| Est. cost (USD / run) | 0.00148 | 0.01791 |

Talking point: Anthropic edged refusal but cost ~12× more and was slower here — a concrete
cost/quality/latency trade-off. Costs use an illustrative price table, so cite them as
relative, not billing-exact.

---

## 10. Deploying to EKS via GitOps (walkthrough)

1. `terraform apply` builds VPC, EKS, node group, 8 ECR repos, ArgoCD + monitoring.
   (If it fails on namespaces with `Unauthorized`, the EKS token expired mid-apply — re-run.)
2. `aws eks update-kubeconfig` to connect `kubectl`.
3. Run the CI pipeline to build + push all 8 images and bump the GitOps tags.
4. `kubectl apply -f gitops/argo-cd.yml` registers the app; ArgoCD syncs.
5. Patch the real `OPENAI_API_KEY` into the cluster secret; run the DB restore Job.
6. Verify: `kubectl get applications -n argocd` -> `Synced / Healthy`; all pods Running.

---

## 11. Key design decisions & tradeoffs

- **EKS over ECS/plain EC2:** industry-standard Kubernetes; cost is complexity.
- **RAG assistant as a separate service:** language-agnostic, independently deployable.
- **LangGraph over a single agent call:** explicit, inspectable, testable-offline reasoning.
- **Mock/live tool switch:** lets the agent be demoed and evaluated with zero AWS spend.
- **OpenAI embeddings passed into Chroma:** simpler, lighter Chroma container.
- **GitOps over `kubectl apply` in CI:** security and auditability.
- **Single small node (then scaled to 2):** cost first; scaled out when pod capacity was hit.

---

## 12. Troubleshooting deep-dive (issue -> cause -> fix -> lesson)

**1. `terraform apply` -> `Unauthorized` on namespaces.** EKS token expired mid-build.
*Fix:* re-run. *Lesson:* provider auth vs token lifetime on long applies.

**2. `Error locating chart ... no cached repo found`.** Empty Helm repo cache.
*Fix:* `helm repo add` + `helm repo update`. *Lesson:* the Helm provider won't fetch indexes for you.

**3. Pods `ImagePullBackOff`: tag not found.** Per-service manifests hardcoded an old tag
while CI pushed under the commit SHA. *Fix:* align manifests to the real ECR tag (Git is the
source of truth), re-sync. *Lesson:* ArgoCD faithfully deploys whatever Git says — including
a dead tag.

**4. New pods `Pending`: "Too many pods".** Single node hit its pod/IP limit during a
rolling update. *Fix:* scale the node group to 2. *Lesson:* instance type caps max pods;
rollouts need headroom.

**5. Backends `CrashLoopBackOff`: `database "auth_db" does not exist` (3D000).** Postgres
starts empty in Kubernetes. *Fix:* run the DB restore Job, restart the services.

**6. `ai-assistant` 401 with `REPLACE_..._KEY`.** ArgoCD self-heal reverted the patched
secret to the Git-committed placeholder. *Fix:* disable auto-sync, patch, restart.
*Lesson:* never commit a placeholder secret to a GitOps repo — use External Secrets /
Secrets Manager and have ArgoCD ignore it.

**7. Windows/Git Bash issues.** MSYS path mangling; `streamlit` not on PATH.
*Fix:* `MSYS_NO_PATHCONV=1`; run `python -m streamlit`. *Lesson:* tooling environment matters.

---

## 13. Likely interview questions

**"Walk me through a deployment."** Push -> Actions builds/pushes 8 images to ECR -> bumps
GitOps tags -> ArgoCD syncs -> pods roll out. CI builds; ArgoCD deploys; decoupled.

**"What is RAG and why use it?"** Retrieve relevant context from a vector store and give it
to the LLM so answers are grounded in real, current data. Here it keeps product/price
answers accurate and lets the assistant answer company-specific policy questions.

**"How did you evaluate it?"** A 26-case suite scoring refusal, retrieval precision, and
faithfulness (LLM-judge held constant, hand-spot-checked). 0.955 / 1.0 / 5.0, with one
honest over-refusal I'd fix in v2.

**"Why LangGraph for Kira?"** It makes the agent's reasoning an explicit, inspectable state
machine with a confidence loop — testable offline (0.938 / 0.938) and demoable via the trace.

**"OpenAI or Anthropic?"** I benchmarked both on the same eval: comparable quality, but
Anthropic cost ~12× more and was slower on this workload — so OpenAI for this use case.

**"Hardest bug?"** The image-tag mismatch: ArgoCD kept deploying a dead tag because the base
manifests hardcoded it — fixed by aligning Git with ECR reality.

**"What would you do in production?"** Remote/locked Terraform state; secrets in a manager
(not Git); multi-node autoscaling with requests/limits; managed DBs; progressive delivery;
alerting + tracing; the assistant behind auth + rate limits.

---

## 14. If I rebuilt it

- Remote Terraform state + locking; secrets in AWS Secrets Manager / External Secrets.
- Multi-node cluster + autoscaler; resource requests/limits; PodDisruptionBudgets.
- Managed RDS per service instead of one in-cluster Postgres.
- Progressive delivery (canary/blue-green) via Argo Rollouts.
- Alerting rules + paging; distributed tracing; OTel spans around LLM calls (P50/P99).
- Assistant: response caching, expanded eval suite, rate limiting, and auth.

---

*Keep this file in `Docs/`. It doubles as project documentation and your interview prep.*