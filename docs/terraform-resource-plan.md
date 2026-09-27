# Terraform resource plan

Phase 1 implements only local Python/React execution. This remains a future resource inventory; no `.tf` files, AWS initialization/plan, credential changes, Bedrock calls, or deployment were added. Favor a small, low-traffic demonstration with bounded usage.

## V1 resource inventory

| Module | Planned resources | Purpose |
|---|---|---|
| bootstrap | Private encrypted/versioned S3 state bucket, TLS policy | Separate state lifecycle; compatible Terraform S3 lockfile support |
| hosting | Private S3 frontend bucket, public access block, CloudFront distribution/OAC, bucket policy, headers policy, CloudFront Function | HTTPS UI; rewrite extensionless SPA routes while missing assets remain 404 |
| auth | Cognito pool, public SPA client, hosted domain | PKCE, no client secret, explicit callbacks, public sign-up disabled |
| api | API Gateway v2 HTTP API, JWT authorizer, stage, routes/integrations, Lambda permissions, access logs | Synchronous routes, restricted CORS, throttles, 30-second integration timeout |
| compute | Three Python 3.12 Lambdas with separate roles/policies | Read, Recommendation, Approval (includes rejection and private mock execution); artifact hashes |
| storage | Private encrypted/versioned S3 history bucket; five on-demand DynamoDB tables and three UI indexes | Synthetic history, campaigns, recommendations, decisions, audit, durable idempotency/receipts; no streams |
| observability | CloudWatch log groups and basic error/throttle alarms | Short retention and request monitoring; optional dashboard, SNS subscription, AWS Budget |
| dns | Optional ACM certificates/validation, Route 53 aliases, optional API custom domain/mapping | Frontend domain and optional API subdomain |

No application events module, DynamoDB Streams, EventBridge bus/rules, reconciler schedule, asynchronous workers, SQS DLQs, or async Lambda failure destinations in V1. Seeding uses an explicit setup script and scoped setup role, not a fourth workflow Lambda. No VPC, NAT gateway, real advertising integration, or public S3 website endpoint is needed.

## IAM boundaries

- Read Lambda: history and application record/index reads. Calculate effective expired/failed statuses without writes.
- Recommendation Lambda: read history/campaign state, invoke configured Bedrock model/profile resources, conditionally write recommendations/request deduplication, append audit. No campaign/approval writes or Approval Lambda invocation. Scope Operations permissions to request records where IAM conditions permit; code enforces exact namespaces.
- Approval Lambda: read history/current state/proposals, write immutable decisions, conditional campaign/recommendation updates, deduplication/action receipts, and append-only audit. No Bedrock access or public raw campaign mutation route.
- Setup role: seed history and conditionally initialize campaign records with audit; explicitly used during future setup, never an unauthenticated API.

Each role writes its own logs. Audit grants omit UpdateItem/DeleteItem. JWT ownership is enforced in handlers and key construction; table-level IAM alone does not establish ownership. Bedrock permissions explicitly identify selected model/profile ARNs, including required destination-region resources. SDK credentials come from IAM roles. Future CI uses OIDC, not long-lived keys.

## Time and cost bounds

Plan 30-second API integration, 25-second Lambda timeout, 20-second application work deadline, and 30-second generation reservation deadline. Bound Bedrock/network calls and SDK retries within the work deadline, reserving time for persistence and response. Verify model latency before a future cloud demo; timeouts never cause automatic approval or fixture fallback. [AWS documents the HTTP API integration limit](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-quotas.html).

Use low configurable reserved concurrency, API throttling, bounded model tokens, on-demand DynamoDB, and no provisioned Lambda concurrency. Logs default to 14-day retention. PITR, dashboards, and budget notifications are configurable choices with documented costs, not local-demo prerequisites. Budget alerts notify rather than cap charges. Local mode makes no AWS calls; deployed infrastructure and model use incur applicable charges.

## Variables and outputs

Inputs: project/environment, region, bedrock_model_id, explicit allowed model/profile ARNs, artifact paths/hashes, allowed UI origins, seed manifest reference, concurrency, token/network timeouts, log retention, optional PITR/monitoring settings. Set BEDROCK_MODEL_ID in Recommendation Lambda from configuration. Other environment values include APP_MODE=aws, bucket/table names, policy/algorithm versions, and log level. No bus/queue names or worker lease settings. Cloud mode rejects fixture reasoning.

Optional hosted_zone_id, frontend_domain, api_domain, alert email. Require corresponding zone/domain configuration. CloudFront certificates use an aliased provider in us-east-1; API certificates use the deployment region. Use a supplied existing hosted zone without registering a domain. CloudFront default URL works without custom DNS. Cognito callbacks/logout URLs match the selected frontend; localhost is development-only.

Outputs: frontend/API URLs, Cognito pool/client/domain, history bucket, table names, optional dashboard URL. No credentials, JWTs, bus names, or queue URLs. Model/region selection remains a later deployment configuration decision.

## Build and lifecycle

Build frontend/Python artifacts before a future apply; no hidden package installs or deployment shell provisioners. Terraform owns all AWS infrastructure including IAM and optional DNS/observability. Static asset publishing and synthetic seeding are later explicit release operations. Pin Terraform/providers, commit locks, and separate bootstrap/application state with environment keys. Disable force-destroy by default. Keep audit, approvals, receipts, and deduplication records until deliberate teardown.

Future checks: terraform fmt, init with backend disabled (provider download may need network), validate, and IAM/configuration assertions. AWS plan/apply and smoke tests are deferred until deployment is requested. No automatic apply pipeline.

## Production Scale Evolution

When asynchronous processing, higher throughput, independent scaling, replay, and stronger failure isolation justify the extra cost, add an events module with EventBridge bus/rules/targets, DynamoDB stream mapping, outbox relay Lambda, scheduled reconciler, separate reasoning/execution workers, and SQS delivery/processing DLQs with policies and failure destinations. Add work/outbox indexes, per-worker IAM, pending-age/dead-letter alarms, and bounded replay controls. Keep persisted human approval verification and atomic mock mutation/audit in the executor. These are future resources, not disabled resources or placeholder modules in V1.

Other references: [CloudFront certificate region](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cnames-and-https-requirements.html), [S3 origin access control](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html), [Bedrock Converse](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html).
