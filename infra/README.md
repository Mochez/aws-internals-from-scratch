# Deploying the real version

This SAM template provisions the *real* AWS equivalent of the toy backend:
DynamoDB instead of `kvstore/store.py`, SNS+SQS instead of `messaging/`.

## Important: this is the final learning checkpoint, not a copy-paste deploy

The Lambda handlers in `src/app/handlers.py` currently talk to the
**in-memory** `KVStore`/`Topic` singletons, on purpose — that's what makes
`src/cli.py` runnable with zero AWS setup. To deploy for real you need to
write a small adapter layer that implements the same interface
(`put_item`/`get_item`/`atomic_increment` on the KVStore side, `publish` on
the topic side) backed by `boto3` DynamoDB/SNS clients, and swap it in via
an environment check (e.g. `if os.environ.get("TABLE_NAME"): use boto3
adapter else: use in-memory`).

This is deliberate: writing that adapter is where the "toy model vs. real
service" comparison becomes concrete — e.g. you'll have to decide how to
express `atomic_increment` as a real `UpdateItem` call with an `ADD`
expression, which is the single most important concept from Phase 1 to
walk away understanding.

## Prerequisites

- AWS account + credentials configured (`aws configure`)
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)

## Deploy

```bash
cd aws-internals-from-scratch
sam build --template infra/template.yaml
sam deploy --guided --stack-name url-shortener-phase1
```

`sam deploy --guided` will prompt for stack name/region and save the config
to `infra/samconfig.toml` (gitignored — don't commit account-specific
config).

## Try it

```bash
curl -X POST "$API_URL/shorten" -d '{"long_url": "https://example.com"}'
curl -i "$API_URL/<code>"        # should 302 redirect
curl "$API_URL/<code>/stats"
```

## Compare against the toy model

While this is deployed, go re-read:
- `src/kvstore/partitioner.py` next to the [DynamoDB partitioning docs](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.Partitions.html)
- `src/messaging/queue.py` next to the [SQS visibility timeout docs](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html)
- `src/messaging/pubsub.py` next to the [SNS-to-SQS fan-out docs](https://docs.aws.amazon.com/sns/latest/dg/sns-sqs-as-subscriber.html)

Write down every place reality surprised you in `../notes/`.

## Tear down

```bash
sam delete --stack-name url-shortener-phase1
```
