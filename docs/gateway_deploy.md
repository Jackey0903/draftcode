# DraftCode Codex Gateway Deployment

DraftCode can expose the local `codex exec` gpt-5.5 path as an OpenAI-compatible
HTTP endpoint:

```text
DraftCode agents -> llm_client -> POST /v1/chat/completions -> gateway -> codex exec
```

The gateway has no third-party Python runtime dependency. It uses
`http.server.ThreadingHTTPServer` and returns `None`/HTTP errors cleanly when Codex
is unavailable.

## Local Commands

Start the gateway:

```bash
export DRAFTCODE_GATEWAY_KEY='<long-random-shared-secret>'
draftcode gateway --host 0.0.0.0 --port 8787
```

Point a DraftCode client at it:

```bash
export DRAFTCODE_LLM_BASE_URL='https://gateway.example.com'
export DRAFTCODE_LLM_API_KEY='<same-long-random-shared-secret>'
draftcode warroom --data-dir data/processed --output-dir outputs/llm
```

Do not set `DRAFTCODE_LLM_BASE_URL` inside the gateway service itself. The gateway
process should call its local Codex CLI, not another gateway.

## Authentication

If `DRAFTCODE_GATEWAY_KEY` is set on the gateway, every request must include:

```http
Authorization: Bearer <key>
```

If the header is missing or wrong, the gateway returns `401`. Keep this enabled
before exposing the endpoint beyond localhost.

## A) EC2 or VPS

1. Create a small EC2/VPS instance and install Python 3.11, git, Node/npm, and the
   Codex CLI using the current official Codex install method. This repository's
   container template uses:

   ```bash
   npm install -g @openai/codex
   ```

2. Clone and install DraftCode:

   ```bash
   git clone <your-private-repo-url> ~/draftcode
   cd ~/draftcode
   python3.11 -m venv .venv
   .venv/bin/pip install -e .
   ```

3. Move Codex authentication from your own machine to your own server. The
   credentials travel only between you and your server, not through DraftCode or
   any third party:

   ```bash
   scp -r ~/.codex user@server:~/
   ssh user@server 'chmod -R go-rwx ~/.codex'
   ```

4. Smoke-test locally on the server:

   ```bash
   cd ~/draftcode
   export DRAFTCODE_GATEWAY_KEY='<long-random-shared-secret>'
   .venv/bin/draftcode gateway --host 127.0.0.1 --port 8787
   ```

5. Install a systemd service. Template:

   ```ini
   [Unit]
   Description=DraftCode Codex Gateway
   After=network-online.target
   Wants=network-online.target

   [Service]
   Type=simple
   User=user
   WorkingDirectory=/home/user/draftcode
   Environment=PATH=/home/user/draftcode/.venv/bin:/home/user/.local/bin:/usr/local/bin:/usr/bin:/bin
   Environment=DRAFTCODE_GATEWAY_KEY=<long-random-shared-secret>
   Environment=DRAFTCODE_GATEWAY_QUIET=1
   ExecStart=/home/user/draftcode/.venv/bin/draftcode gateway --host 127.0.0.1 --port 8787
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

   Enable it:

   ```bash
   sudo install -m 0644 draftcode-gateway.service /etc/systemd/system/draftcode-gateway.service
   sudo systemctl daemon-reload
   sudo systemctl enable --now draftcode-gateway
   sudo journalctl -u draftcode-gateway -f
   ```

6. Optional public exposure with Cloudflare Tunnel:

   ```bash
   cloudflared tunnel create draftcode-gateway
   cloudflared tunnel route dns draftcode-gateway gateway.example.com
   ```

   Example `~/.cloudflared/config.yml`:

   ```yaml
   tunnel: draftcode-gateway
   credentials-file: /home/user/.cloudflared/<tunnel-id>.json
   ingress:
     - hostname: gateway.example.com
       service: http://127.0.0.1:8787
     - service: http_status:404
   ```

   Keep `DRAFTCODE_GATEWAY_KEY` enabled even when Cloudflare Access or firewall
   rules are also in place.

## B) Fargate

Use `Dockerfile.gateway` as the container entrypoint. The image installs the Codex
CLI and DraftCode, then starts:

```bash
draftcode gateway --host 0.0.0.0 --port 8787
```

Build and push:

```bash
aws ecr create-repository --repository-name draftcode-gateway
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com
docker build -f Dockerfile.gateway -t draftcode-gateway .
docker tag draftcode-gateway:latest <account>.dkr.ecr.us-east-1.amazonaws.com/draftcode-gateway:latest
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/draftcode-gateway:latest
```

Codex uses ChatGPT subscription OAuth credentials. Mount `~/.codex` on persistent
EFS so token refreshes can be written back:

```json
{
  "volumes": [
    {
      "name": "codex-home",
      "efsVolumeConfiguration": {
        "fileSystemId": "fs-xxxxxxxx",
        "transitEncryption": "ENABLED",
        "authorizationConfig": {
          "accessPointId": "fsap-xxxxxxxx",
          "iam": "ENABLED"
        }
      }
    }
  ],
  "containerDefinitions": [
    {
      "name": "gateway",
      "image": "<account>.dkr.ecr.us-east-1.amazonaws.com/draftcode-gateway:latest",
      "portMappings": [{"containerPort": 8787, "protocol": "tcp"}],
      "environment": [
        {"name": "DRAFTCODE_GATEWAY_QUIET", "value": "1"}
      ],
      "secrets": [
        {
          "name": "DRAFTCODE_GATEWAY_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:<account>:secret:draftcode/gateway-key"
        }
      ],
      "mountPoints": [
        {
          "sourceVolume": "codex-home",
          "containerPath": "/home/draftcode/.codex",
          "readOnly": false
        }
      ]
    }
  ]
}
```

Recommended Fargate shape:

- ECS Service running the gateway task in private subnets.
- EFS Access Point mounted at `/home/draftcode/.codex` with read/write enabled.
- Internal ALB or ECS Service Connect in front of the task.
- API Gateway HTTP API with VPC Link to the ALB/service endpoint.
- `DRAFTCODE_GATEWAY_KEY` stored in Secrets Manager and injected into the task.

## Codex OAuth Operations

Codex CLI authentication is ChatGPT subscription OAuth. Operationally:

- Tokens must live on persistent disk because automatic refresh writes back into
  `~/.codex`.
- On EC2/VPS, that persistent disk is the instance home directory.
- On Fargate, use EFS mounted at `/home/draftcode/.codex`.
- If the refresh token expires or is revoked, the user must log in again and update
  the server/EFS copy of `~/.codex`.
- Do not bake `~/.codex` into the image and do not commit it to git.

## Client Cutover

Local or cloud DraftCode clients switch to the remote gateway with:

```bash
export DRAFTCODE_LLM_BASE_URL='https://gateway.example.com'
export DRAFTCODE_LLM_API_KEY='<gateway-key>'
```

Unset `DRAFTCODE_LLM_BASE_URL` to return to the local `codex exec` path. Set
`DRAFTCODE_LLM_DISABLED=1` to force deterministic fallbacks.
