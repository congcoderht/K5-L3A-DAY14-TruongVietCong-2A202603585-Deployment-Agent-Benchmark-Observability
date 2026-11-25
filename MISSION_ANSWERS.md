# Day 14 Lab - Mission Answers

> **Họ tên:** Trương Việt Công
> **MSSV:** 2A202603585
> **Lớp:** K5-L3A

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns phát hiện trong `01-localhost-vs-production/develop/app.py`

1. **Hardcode secrets trong source code (dòng 17–18):** `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` và `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`. Nếu push lên GitHub (repo public), thông tin nhạy cảm bị lộ ngay lập tức. Ở `production/config.py` (dòng 27, 32), các biến này được đọc từ biến môi trường qua `os.getenv(...)`.
2. **Hardcode cấu hình ứng dụng (dòng 21–22):** `DEBUG = True` và `MAX_TOKENS = 500` viết cứng trong code, không thể thay đổi linh hoạt giữa các môi trường `development`, `staging`, `production` theo chuẩn 12-Factor. Ở `production/config.py` (dòng 19–29), toàn bộ cấu hình được gom vào `Settings` đọc từ env vars và kiểm tra sớm qua `validate()`.
3. **Dùng `print()` thay cho structured logging và log lộ secret (dòng 33–34, 38):** Dùng `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` khiến log không có cấu trúc JSON để công cụ giám sát (Loki, Datadog...) parse/lọc và nghiêm trọng hơn là làm rò rỉ API key ra stdout. Ở `production/app.py` (dòng 28–32, 111–122), ứng dụng dùng `logging` định dạng JSON và chỉ ghi metadata (`question_length`, `client_ip`, `response_length`).
4. **Không có Health check / Readiness endpoint (dòng 42–43):** Thiếu `/health` và `/ready` nên nền tảng cloud hoặc load balancer không biết container còn sống hay đã sẵn sàng nhận traffic để tự restart hoặc điều phối request. Ở `production/app.py` (dòng 135–161), đã có đủ `GET /health` và `GET /ready`.
5. **Bind `localhost`, hardcode `port=8000` và bật `reload=True` (dòng 49–54):** `host="localhost"` làm container/cloud không nhận được kết nối từ bên ngoài; `port=8000` cố định bỏ qua biến `PORT` do nền tảng (Railway/Render) cấp; `reload=True` gây tốn tài nguyên và không an toàn trên production. Ở `production/app.py` (dòng 194–199), server bind `settings.host` (`0.0.0.0`), đọc `settings.port`, và chỉ bật `reload=settings.debug`.
6. **Không xử lý Graceful shutdown và thiếu kiểm tra input/CORS:** Bản `develop` tắt đột ngột khi nhận `SIGTERM`, dễ cắt ngang request đang chạy; bản `production/app.py` dùng `lifespan` (dòng 39–67) kết hợp `signal.signal(signal.SIGTERM, handle_sigterm)` (dòng 180–189), cấu hình `CORSMiddleware` (dòng 77–82), và kiểm tra `question` rỗng trả `422` (dòng 107–108).

### Exercise 1.2: Kết quả chạy bản `develop`

Lệnh test (`POST /ask` nhận query parameter `question`):

```text
$ curl -i -X POST "http://localhost:8000/ask?question=Hello"
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 08:39:49 GMT
server: uvicorn
content-length: 103
content-type: application/json

{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

Log server bản `develop` (lộ secret ra console):

```text
[DEBUG] Got question: Hello
[DEBUG] Using key: sk-hardcoded-fake-key-never-do-this
[DEBUG] Response: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.
```

Kết quả test nhanh bản `production` (`/health`, `/ready`, `/ask`):

```text
$ curl -i http://localhost:8000/health
HTTP/1.1 200 OK
{"status":"ok","uptime_seconds":93.0,"version":"1.0.0","environment":"development","timestamp":"2026-11-25T08:43:59.911344+00:00"}

$ curl -i http://localhost:8000/ready
HTTP/1.1 200 OK
{"ready":true}

$ curl -i -X POST "http://localhost:8000/ask" -H "Content-Type: application/json" -d '{"question": "Hello"}'
HTTP/1.1 200 OK
{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","model":"gpt-4o-mini"}
```

### Exercise 1.3: Bảng so sánh `develop` vs `production`

| Feature | Develop | Production | Tại sao quan trọng? |
| --- | --- | --- | --- |
| **Config & Secrets** | Hardcode `OPENAI_API_KEY`, `DEBUG`, `MAX_TOKENS` ngay trong `develop/app.py` (dòng 17–22) | Đọc từ biến môi trường qua `Settings` trong `production/config.py` (dòng 15–50) và `.env` | Tránh lộ secret lên Git; đổi được cấu hình giữa dev/staging/prod mà không cần sửa hay build lại code |
| **Health check** | Không có (`develop/app.py` dòng 42–43) | Có `GET /health` và `GET /ready` (`production/app.py` dòng 135–161) | Giúp platform/Docker/Load Balancer phát hiện container treo để tự restart (`/health`) và chỉ route traffic khi app sẵn sàng (`/ready`) |
| **Logging** | Dùng `print()` dạng text tự do, in cả `OPENAI_API_KEY` (`develop/app.py` dòng 33–38) | Structured JSON logging qua `logging` (`production/app.py` dòng 28–32, 111–122), không log secret | Log JSON dễ thu thập, tìm kiếm, tạo cảnh báo trên Datadog/Loki; tránh rò rỉ thông tin nhạy cảm |
| **Shutdown** | Tắt đột ngột | Graceful shutdown với `lifespan` và `signal.signal(signal.SIGTERM, handle_sigterm)` (`production/app.py` dòng 39–67, 180–189) | Cho phép các request đang xử lý hoàn thành trước khi process thoát khi deploy/scale down, tránh lỗi 502/mất dữ liệu |
| **Network & Server** | `host="localhost"`, `port=8000` cứng, `reload=True` (`develop/app.py` dòng 49–54) | `host=settings.host` (`0.0.0.0`), `port=settings.port`, `reload=settings.debug` (`production/app.py` dòng 194–199) | `0.0.0.0` cần thiết để chạy trong container; `PORT` động theo cloud platform; tắt `reload` để ổn định và hiệu năng cao |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions (`02-docker/develop/Dockerfile`)

1. **Base image là gì?** `python:3.11` (chứa OS Debian đầy đủ và Python 3.11 runtime + build tools; ở bản `production/Dockerfile` tối ưu thành `python:3.11-slim`).
2. **Working directory là gì?** `/app` (`WORKDIR /app`), là thư mục làm việc mặc định bên trong container nơi code được copy vào và chạy lệnh `CMD`.
3. **Tại sao `COPY requirements.txt` đứng trước `COPY . .` / `COPY app.py`?** Để tận dụng **Docker layer cache**: nếu chỉ sửa source code mà không thay đổi `requirements.txt`, Docker dùng lại cache của bước `pip install` thay vì tải và cài lại toàn bộ thư viện từ đầu.
4. **`CMD` vs `ENTRYPOINT` khác nhau thế nào?** `CMD` là lệnh mặc định có thể bị **ghi đè** dễ dàng khi truyền tham số lúc `docker run <image> <lệnh khác>`, còn `ENTRYPOINT` cố định file/lệnh thực thi chính của container (tham số truyền thêm ở `docker run` chỉ được nối vào làm đối số cho `ENTRYPOINT`).

### Exercise 2.2 & 2.3: Build, test container và so sánh dung lượng image

Kết quả chạy container `my-agent:develop`:

```text
$ curl -i -X POST "http://localhost:8000/ask?question=Hello"
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 08:53:54 GMT
server: uvicorn
content-length: 126
content-type: application/json

{"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

Kết quả đo kích thước từ `docker images | grep my-agent`:

```text
my-agent:advanced                   2f1b19500f23        240MB         57.4MB
my-agent:develop                    e751a5797126       1.67GB          426MB
```

* **Develop (`my-agent:develop`):** `1.67 GB` (`1,670 MB`, content size `426 MB`)
* **Production (`my-agent:advanced`):** `240 MB` (content size `57.4 MB`)
* **Chênh lệch:** Giảm `(1670 - 240) / 1670 ≈ 85.6%` tổng dung lượng image (và giảm `86.5%` ở content size).
* **Giải thích multi-stage (`02-docker/production/Dockerfile`):**
  * **Stage 1 (`builder`):** Dùng `python:3.11-slim`, cài `gcc`, `libpq-dev` và chạy `pip install --user` để biên dịch dependencies vào `/root/.local`.
  * **Stage 2 (`runtime`):** Tạo lại từ `python:3.11-slim` sạch, chỉ copy các gói đã cài từ `/root/.local` sang `/home/appuser/.local` cùng source code, chạy bằng user non-root `appuser` và có `HEALTHCHECK`. Nhờ bỏ hoàn toàn `gcc`, `libpq-dev`, apt cache và dùng `-slim` thay vì full `python:3.11`, image giảm từ `1.67 GB` xuống còn `240 MB`.

### Exercise 2.4: Docker Compose stack (`02-docker/production/docker-compose.yml`)

**Sơ đồ kiến trúc:**

```text
Client ──(HTTP :80)──▶ Nginx (reverse proxy / LB, network: internal)
                          │
                          ▼ (:8000)
                       Agent (FastAPI, target: runtime, healthcheck)
                          ├──▶ Redis (redis:7-alpine :6379, volume: redis_data)
                          └──▶ Qdrant (qdrant/qdrant:v1.9.0 :6333, volume: qdrant_data)
```

*Các service (`agent`, `redis`, `qdrant`, `nginx`) giao tiếp với nhau qua mạng bridge nội bộ `internal` bằng tên service; chỉ `nginx` mở cổng `80`/`443` ra host.*

**Kết quả test qua Nginx (cổng 80):**

```text
$ curl -i http://localhost/health
HTTP/1.1 200 OK
Server: nginx
Date: Wed, 25 Nov 2026 08:55:42 GMT
Content-Type: application/json
Content-Length: 96
Connection: keep-alive
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block

{"status":"ok","uptime_seconds":20.2,"version":"2.0.0","timestamp":"2026-11-25T08:55:42.200718"}

$ curl -i -X POST http://localhost/ask -H "Content-Type: application/json" -d '{"question": "Explain microservices"}'
HTTP/1.1 200 OK
Server: nginx
Date: Wed, 25 Nov 2026 08:56:08 GMT
Content-Type: application/json
Content-Length: 126
Connection: keep-alive
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block

{"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

---

## Part 3: Cloud Deployment

### Exercise 3.1: Deploy Agent Part 6 lên Railway

* **Platform:** Railway (`06-lab-complete/` kết nối với service `Redis` trên Railway)
* **Public URL:** https://prolific-unity-production-0b2b91ea.up.railway.app
* **Screenshots:**
  * [screenshots/dashboard.png](screenshots/dashboard.png)
  * [screenshots/running.png](screenshots/running.png)
  * [screenshots/test.png](screenshots/test.png)

**Kết quả 4 lệnh tự kiểm tra CP6 (chạy từ WSL2 tới URL public, không lộ key):**

```text
$ curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
200

$ curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
200

$ curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'
401

$ curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'
200
```

### Exercise 3.2: So sánh `06-lab-complete/railway.toml` và `06-lab-complete/render.yaml`

| Tiêu chí | `railway.toml` | `render.yaml` | Vì sao khác nhau? |
| --- | --- | --- | --- |
| **Định dạng & phạm vi** | TOML (`[build]`, `[deploy]`), cấu hình cho **1 service** hiện tại | YAML (`services:`), là **Blueprint IaC** có thể khai báo cả danh sách nhiều service (web, worker, database) | Railway quản lý tài nguyên (như Redis) trong Project Canvas/CLI rồi nối qua Variable Reference; Render cho phép mô tả toàn bộ stack trong một Blueprint file |
| **Cách build** | `builder = "DOCKERFILE"`, `dockerfilePath = "Dockerfile"` | `runtime: docker`, `dockerfilePath: ./Dockerfile` | Cả hai đều trỏ tới cùng `Dockerfile` multi-stage của agent nhưng theo schema riêng của từng nền tảng |
| **Health check & restart** | `healthcheckPath = "/health"`, `healthcheckTimeout = 30`, `restartPolicyType = "ON_FAILURE"` | `healthCheckPath: /health` | Railway dùng camelCase chữ thường `healthcheckPath` và cho chỉnh timeout/restart policy trực tiếp trong TOML; Render dùng `healthCheckPath` |
| **Biến môi trường & secrets** | Không cần liệt kê trong `railway.toml`; đặt qua Railway Dashboard (`Variables`) hoặc `railway variables set` | Khai báo trực tiếp trong `envVars:` với `generateValue: true` (tự sinh secret như `AGENT_API_KEY`) hoặc `sync: false` (nhập tay trên UI khi deploy, như `REDIS_URL`) | Giúp Render tạo Blueprint từ repo public mà không phải hardcode bất kỳ secret nào vào Git |

### Exercise 3.3: Pipeline CI/CD trên GCP Cloud Run (`03-cloud-deployment/production-cloud-run/`)

Đọc `cloudbuild.yaml` và `service.yaml`, pipeline CI/CD tự động hóa 4 bước từ lúc push code lên nhánh `main`:
1. **`test`:** Dùng container `python:3.11-slim` cài dependencies và chạy `pytest tests/ -v`; nếu test fail pipeline dừng ngay.
2. **`build`:** Chờ `test` xong rồi build Docker image gắn hai tag (`$COMMIT_SHA` để rollback chính xác và `latest` để tận dụng layer cache `--cache-from`).
3. **`push`:** Đẩy image với các tag vừa build lên Google Container Registry (`gcr.io/$PROJECT_ID/ai-agent`).
4. **`deploy`:** Chạy `gcloud run deploy` triển khai image `$COMMIT_SHA` lên Cloud Run vùng `asia-southeast1` (`--min-instances=1` tránh cold start, `--max-instances=10`, `512Mi` RAM, 1 CPU, nạp secret từ GCP Secret Manager). Ngoài ra `service.yaml` định nghĩa cấu hình Knative dưới dạng IaC (concurrency `80`, timeout `60s`, secret refs từ Secret Manager, `livenessProbe` gọi `/health` và `startupProbe` gọi `/ready`).

---

## Part 4: API Security

### Exercise 4.1: API Key authentication (`04-api-gateway/develop/app.py`)

* **API key được check ở đâu:** Trong dependency `verify_api_key` (`04-api-gateway/develop/app.py` dòng 39–54) đọc header `X-API-Key` bằng `APIKeyHeader` và inject vào route `@app.post("/ask")` qua `Depends(verify_api_key)` (dòng 70).
* **Khi thiếu hoặc sai key:** Thiếu header `X-API-Key` trả `401 Unauthorized`; sai key trả `403 Forbidden`. (Ở Part 6 production chuẩn hóa cả thiếu và sai về `401`).
* **Cách rotate key:** Đọc `AGENT_API_KEY` từ biến môi trường (`os.getenv`), hoặc hỗ trợ danh sách key cũ + mới song song trong giai đoạn chuyển đổi rồi mới gỡ key cũ trên cloud dashboard.

**Kết quả test thực tế (`AGENT_API_KEY=secret-key-123 python app.py`):**

```text
$ curl -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question": "Hello"}'
HTTP/1.1 401 Unauthorized
date: Wed, 25 Nov 2026 08:59:15 GMT
server: uvicorn
content-length: 67
content-type: application/json

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

$ curl -i -X POST http://localhost:8000/ask -H "X-API-Key: secret-key-123" -H "Content-Type: application/json" -d '{"question": "Hello"}'
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 08:59:57 GMT
server: uvicorn
content-length: 122
content-type: application/json

{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

### Exercise 4.2 & 4.3: JWT Authentication & Rate Limiting (`04-api-gateway/production/`)

* **JWT flow (`auth.py`):** Client gửi `username`/`password` (`student` / `demo123`) tới `POST /auth/token` → server xác thực và ký JWT (`HS256`, hạn 60 phút, payload chứa `sub`, `role`, `iat`, `exp`) → client đính kèm `Authorization: Bearer <TOKEN_REDACTED>` khi gọi `POST /ask` → `verify_token` kiểm tra chữ ký stateless không cần truy vấn DB mỗi request.
* **Rate limiter (`rate_limiter.py`):**
  * **Thuật toán:** **Sliding Window Counter** dùng `collections.deque` lưu timestamp của các request trong cửa sổ `window_seconds = 60` (xóa các timestamp cũ hơn `now - 60`).
  * **Giới hạn theo role:** User thường (`student`) = `10 req/phút` (`rate_limiter_user`); Admin (`teacher`) = `100 req/phút` (`rate_limiter_admin`). Khi vượt ngưỡng trả `429 Too Many Requests` kèm headers `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `Retry-After`.
  * **Lưu ý production:** `rate_limiter.py` demo đang lưu `_windows` trong RAM nên khi restart hoặc chạy nhiều instance sẽ mất/lệch state — trên production (Part 6) cần lưu trong **Redis**.

**Kết quả test vòng lặp 12 requests với JWT của `student` (đã che token):**

```text
$ TOKEN="<TOKEN_REDACTED>"
$ for i in $(seq 1 12); do
    curl -i -s -X POST http://localhost:8000/ask -H "Authorization: Bearer $TOKEN" ...
  done

=== Request 1 ===
HTTP/1.1 200 OK
...
{"question":"Test 1","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.","usage":{"requests_remaining":9,"budget_remaining_usd":1.6e-05}}

=== Request 10 ===
HTTP/1.1 200 OK
...
{"question":"Test 10","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.","usage":{"requests_remaining":0,"budget_remaining_usd":0.000191}}

=== Request 11 ===
HTTP/1.1 429 Too Many Requests
date: Wed, 25 Nov 2026 09:02:26 GMT
server: uvicorn
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: 1795597406
retry-after: 57
content-length: 98
content-type: application/json
...

=== Request 12 ===
HTTP/1.1 429 Too Many Requests
...
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
retry-after: 57
```

### Exercise 4.4: Cost Guard & Tại sao cần cả Rate Limit lẫn Cost Guard

* **Cách hoạt động (`cost_guard.py`):** Trước khi gọi LLM, `check_budget(user_id)` kiểm tra chi phí đã dùng của user (`daily_budget_usd = $1.0`) và tổng hệ thống (`global_daily_budget_usd = $10.0`); nếu vượt ngân sách user trả `402 Payment Required` (vượt global trả `503`), đạt 80% ghi log cảnh báo. Sau khi LLM trả lời, `record_usage()` cộng dồn input/output tokens và quy đổi ra USD. Khi triển khai thật (Part 6), tổng chi phí theo ngày/tháng được lưu trong **Redis** (dùng `INCRBYFLOAT` + `EXPIRE`) để chia sẻ giữa mọi instance và không mất khi restart.
* **Vì sao cần cả hai:**
  * **Rate limit** bảo vệ **tốc độ / tải hệ thống** (chống spam burst, DDoS theo số request/phút).
  * **Cost guard** bảo vệ **ví tiền** (ngân sách USD). Một kẻ tấn công hoặc user gửi chậm nhưng gửi prompt rất dài/output đắt tiền vẫn có thể lọt qua rate limit và làm cháy ngân sách LLM nếu thiếu cost guard.

---

## Part 5: Scaling & Reliability

### Exercise 5.1 & 5.2: Health Checks (`/health`, `/ready`) & Graceful Shutdown (`05-scaling-reliability/develop/app.py`)

* **Liveness (`/health`) vs Readiness (`/ready`) khác nhau ở đâu:**
  * **`GET /health` (Liveness probe):** Kiểm tra *"process/container còn sống không?"*. Nếu `/health` lỗi hoặc timeout, platform (Docker, Railway, Render, Kubernetes) sẽ **restart container**. Không nên trả 503 ở `/health` chỉ vì Redis tạm thời rớt nếu process vẫn đang chạy.
  * **`GET /ready` (Readiness probe):** Kiểm tra *"agent đã sẵn sàng nhận traffic chưa?"* (đã khởi tạo xong, Redis/dependencies đã kết nối chưa). Load balancer dựa vào `/ready` để **ngừng route traffic mới** (khi trả `503`) trong lúc container đang khởi động, đang shutdown (`_is_ready = False`), hoặc mất kết nối Redis.
* **Graceful shutdown (`SIGTERM`):**
  * Khi platform gửi tín hiệu `SIGTERM` (khác với `SIGKILL` giết tiến trình ngay lập tức), handler và `lifespan` trong `develop/app.py` (dòng 54–66, 175–187) đặt `_is_ready = False` để chặn traffic mới, theo dõi `_in_flight_requests` và chờ các request đang chạy hoàn thành (trong `timeout_graceful_shutdown=30` của uvicorn) trước khi đóng kết nối và thoát sạch.

### Exercise 5.3–5.5: Stateless Design, Load Balancing & `test_stateless.py`

* **Vì sao lưu state trong RAM hỏng khi chạy nhiều instance:** Khi scale ra 3 container (`--scale agent=3`), mỗi container có vùng nhớ RAM riêng biệt. Nếu lưu lịch sử hội thoại hay rate-limit counter trong `dict` của Python ở RAM, request 1 vào `instance-A` và request 2 qua Nginx load balancer rơi vào `instance-B` sẽ không thấy dữ liệu của nhau (mất ngữ cảnh hội thoại, sai lệch bộ đếm). Giải pháp là chuyển toàn bộ shared state sang **Redis**.
* **Kết quả chạy `docker compose -p k5-day14-scaling up -d --build --scale agent=3` và `python test_stateless.py` (cổng `8080`, endpoint `POST /chat`):**

```text
Session ID: 9eb8d251-8d6c-4540-9454-db12208cd8c3

Request 1: [instance-e0e845]  Q: What is Docker?
Request 2: [instance-4bbc5f]  Q: Why do we need containers?
Request 3: [instance-d05015]  Q: What is Kubernetes?
Request 4: [instance-e0e845]  Q: How does load balancing work?
Request 5: [instance-4bbc5f]  Q: What is Redis used for?

Total requests: 5
Instances used: {'instance-e0e845', 'instance-4bbc5f', 'instance-d05015'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10
✅ Session history preserved across all instances via Redis!
```

* **Giải thích kết quả:** 5 request trong cùng 1 `session_id` được Nginx phân phối luân phiên tới cả **3 instance khác nhau** (`instance-e0e845`, `instance-4bbc5f`, `instance-d05015`), nhưng khi truy vấn `/chat/{session_id}/history` vẫn nhận đủ **10 tin nhắn** (5 câu hỏi `user` + 5 câu trả lời `assistant`) theo đúng thứ tự. Điều này chứng minh state đã hoàn toàn tách khỏi RAM từng container và đồng bộ qua Redis.

---

## Part 6: Checklist Deliverable (`check_production_ready.py`)

```text
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
```

*Thông số đo thực tế từ `python check_production_ready.py`: Docker image `56 MB`, build `18s`, `docker stop` thoát với `exit code 0` trong `1.2s`, rate limiting `429` sau `5` request thành công và giữ nguyên sau restart nhờ Redis.*

---

## AI Log

* **CP1 — Localhost vs Production:** Hỏi AI hướng dẫn từng bước thiết lập WSL2, Python `venv` và kiểm tra đối chiếu `01-localhost-vs-production/develop/app.py` với `production/app.py`. AI gợi ý danh sách anti-pattern và khung bảng so sánh; tôi tự chạy cả hai server trên WSL2 (`curl` `/ask`, `/health`, `/ready`), đối chiếu số dòng code và ghi kết quả thật vào Part 1.
* **CP2 — Docker:** Hỏi AI các lệnh build từ gốc repo, cấu hình `.env.local` và chạy Docker Compose với `-p`. Tôi tự build 2 image, đo dung lượng thật (`1.67GB` vs `240MB`), chạy test container và stack Nginx trên WSL2, sau đó đối chiếu lại `Dockerfile` và `docker-compose.yml` để hoàn thiện câu trả lời Part 2.
* **CP3 — API Security:** Hỏi AI cách chạy và test bản `develop` (API key) và bản `production` (`/auth/token` cho `student`/`demo123`, vòng lặp `curl -i` kiểm tra `429`). Tôi tự chạy server, thu được output `401`, `200` (10 lần đầu) và `429` (`Retry-After: 57` ở request 11–12), đọc đối chiếu `auth.py`, `rate_limiter.py`, `cost_guard.py` để viết phần giải thích và che token trước khi lưu.
* **CP4 — Scaling & Reliability:** Hỏi AI lệnh chạy stack 3 instance với `-p k5-day14-scaling` và kiểm tra stateless. Tôi tự chạy `docker compose up --scale agent=3` và `python test_stateless.py`, xác nhận 5 request đi qua cả 3 instance mà vẫn giữ nguyên 10 message history trong Redis, đối chiếu code `05-scaling-reliability/develop/app.py` để giải thích `/health` vs `/ready` và graceful shutdown.
* **CP5 — Part 6 Final Project (`06-lab-complete/`):** Hỏi AI cách hoàn thiện các module TODO trong `06-lab-complete/app/` (`config.py`, `redis_client.py`, `auth.py`, `rate_limiter.py`, `cost_guard.py`, `main.py`) cùng `Dockerfile` multi-stage, `docker-compose.yml`, `.dockerignore`, `.env.example`, `railway.toml` và `render.yaml`. Tôi đã đọc hiểu các file code, tự cài dependencies và chạy `python check_production_ready.py` trong WSL2, đạt `PASS 12/12` (`43/43 checks passed`, image `56 MB`, `docker stop` `1.2s`).
* **CP6 — Part 3 Cloud Deployment:** Hỏi AI cách xử lý lỗi tên service quá dài trên Railway (tạo Empty Service rồi Connect Repo với Root Directory `/06-lab-complete`), cách nối `REDIS_URL` sang service `prolific-unity` và sửa lỗi `502` do lệch Target Port (`8000` vs `PORT=8080` của Railway). Sau khi chỉnh Port `8080`, tôi tự chạy 4 lệnh `curl` tới URL public và xác nhận kết quả `200`, `200`, `401`, `200`; đối chiếu `railway.toml`, `render.yaml`, `cloudbuild.yaml`, `service.yaml` để hoàn thiện Part 3 và `DEPLOYMENT.md`.
* **CP7 & CP8 — Part 7 Benchmark & Observability:** Hỏi AI hướng dẫn chạy load test (`load_test.py` ở 4 mức concurrency và 3 mức `MOCK_SLOW_RATE`), eval (`run_eval.py`), sửa `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` (và đồng bộ sang `production/utils/mock_llm.py`), sửa lỗi `Dockerfile` của `benchmark-observability/production/` (chuyển cài đặt thư viện sang `/usr/local` để user `agent` tìm thấy `uvicorn`), và chạy Locust headless (`scale_1`, `scale_3`), Grafana, Jaeger, Prometheus Alerts. Toàn bộ số liệu trong `BENCHMARK_REPORT.md` đều lấy trực tiếp từ 10 file JSON trong `reports/`, 2 file CSV trong `benchmark-results/` và các ảnh tự chụp trong `screenshots/`.
