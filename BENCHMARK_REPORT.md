# Benchmark & Observability Report — Day 14

> Mọi con số phải lấy từ report JSON / CSV / screenshot thật, không ước lượng.

**Họ tên:** Trương Việt Công — MSSV: 2A202603585 (Lớp K5-L3A)
**Ngày chạy:** 2026-11-25
**Môi trường:** Windows 11 + WSL2 Ubuntu (Python 3.12.3, Docker Desktop)

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Đảm bảo 95% người dùng nhận phản hồi dưới 0.5 giây, giữ trải nghiệm mượt ngay cả khi có ~3% request chậm đuôi |
| Error rate `/ask` | < 2 % | Cho phép error budget 2% để chịu được lỗi thoáng qua, nhưng phát hiện sớm trước khi ảnh hưởng diện rộng |
| Accuracy trên golden dataset | ≥ 100 % (tối thiểu ≥ 80% quality gate) | Đảm bảo mọi câu hỏi chuẩn đều có câu trả lời đúng keyword và không bị regression giữa các phiên bản |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.51 | 189.3 | 220.6 | 1704.4 | 2.33% | FAIL (error rate > 2%) |
| 10 | 41.84 | 191.3 | 221.0 | 1700.9 | 0.33% | PASS |
| 50 | 100.51 | 211.3 | 343.6 | 1710.1 | 0.00% | PASS |
| 100 | 57.70 | 605.2 | 3573.4 | 3961.3 | 0.67% | FAIL (p95 > 500ms) |

**Nhận xét:** RPS **không** tăng tuyến tính theo concurrency. Từ `c=1` (`4.51 req/s`) lên `c=10` (`41.84 req/s`) tăng gần tuyến tính (~9.3 lần) và đạt đỉnh `100.51 req/s` ở `c=50` (p95 vẫn dưới `343.6 ms`). Tuy nhiên tới `c=100`, 1 process uvicorn/event loop bị bão hòa hàng đợi kết nối và chi phí chuyển ngữ cảnh, khiến RPS **tụt xuống còn `57.70 req/s`** và latency tăng vọt (`p50 = 605.2 ms`, `p95 = 3573.4 ms`).

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 191.0 | 217.6 | 223.1 |
| 0.03 (mặc định) | 210.7 | 219.0 | 1656.3 |
| 0.1 | 304.4 | 1678.3 | 1708.5 |

**Nhận xét:** `p99` và `p95` nhạy nhất với request chậm: khi nâng `MOCK_SLOW_RATE` từ `0` lên `0.03` (chỉ 3% request chậm), `avg` gần như không đổi nhiều (`191.0 ms` → `210.7 ms`), `p95` giữ nguyên (`219.0 ms`), nhưng `p99` nhảy vọt gấp **7.4 lần** lên `1656.3 ms`. Tới `0.1` (10% request chậm > ngưỡng 5%), cả `p95` cũng vọt lên `1678.3 ms` trong khi `avg` mới là `304.4 ms`. Vì **average che giấu nhóm người dùng bị chậm ở phần đuôi (tail latency)**, SLO phải đặt theo `p95`/`p99`.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.35% (1/23) | 91.30% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 57.0 | 109.0 | 114.1 |
| Tổng cost (USD) | $0.000402 | $0.000760 | $0.000794 |
| Cost / câu đúng (USD) | $0.00040215 | $0.00003619 | $0.00003453 |
| Quality gate | FAIL | PASS (≥ 80%) | PASS (≥ 100%, 0 regression) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm entry `(["jwt", "xác thực"], ...)` vào `KNOWLEDGE_BASE` trong `utils/mock_llm.py` giải thích JWT là token stateless có chữ ký số và thời gian hết hạn (`exp`), khác API key tĩnh |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm entry `(["hpa", "kubernetes"], ...)` vào `KNOWLEDGE_BASE` giải thích Kubernetes HPA tự scale theo CPU, memory hoặc custom metrics |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

`v2` tốn thêm bước retrieval (~20 ms) và nạp thêm context vào prompt nên lượng token trung bình tăng khoảng **2 lần** (`57.0` → `114.1` tokens/câu) và tổng chi phí tăng gần gấp đôi (`$0.000402` → `$0.000794`). Đổi lại, độ chính xác nhảy vọt từ **`4.35%` lên `100.0%`**, giúp **chi phí trên mỗi câu trả lời đúng (`cost / câu đúng`) rẻ hơn ~11.6 lần** (`$0.00003453` so với `$0.00040215`). Đây là chỉ số công bằng nhất để đánh giá hiệu quả thực sự của RAG.

**Quality gate trong CI/CD (chặn merge khi có regression):**

`eval/run_eval.py` trả về **exit code `0`** khi đạt ngưỡng `--min-accuracy` và không bị regression so với `--baseline`, và trả **exit code `1`** khi không đạt hoặc tụt accuracy. Trong GitHub Actions, thêm job chạy `run_eval.py` trước khi cho phép merge PR:

```yaml
eval-quality-gate:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: { python-version: "3.11" }
    - run: pip install -r 06-lab-complete/benchmark-observability/develop/requirements.txt
    - name: Run agent v2 & eval quality gate
      working-directory: 06-lab-complete/benchmark-observability/develop
      run: |
        AGENT_VERSION=v2 MOCK_ERROR_RATE=0 python app.py &
        PID=$!
        sleep 3
        python eval/run_eval.py --url http://localhost:8000 --min-accuracy 1.0 --baseline reports/eval_v2.json
        STATUS=$?
        kill $PID
        exit $STATUS
```

---

## 4. Observability stack (production)

### 4.1 Screenshot & đọc số liệu Grafana

- [x] Dashboard Grafana khi đang có tải (`screenshots/grafana-dashboard.png`): Traffic `17.1 req/s` (~`8.5 req/s` mỗi instance trên 2 instance `172.18.0.7:8000` và `172.18.0.8:8000`), Error rate `0.53%`, Latency `p95 = 296.04 ms`, Saturation `5` in-flight requests, LLM cost 1h `$1.2238`, Retrieval hit ratio `100%` (`v2`, `mock-llm-small`).
- [x] Một trace chậm trong Jaeger (`screenshots/jaeger-slow-trace.png`): tổng `3.3s`, span `chat mock-llm-small` mất `1643.8 ms`.
- [x] Một trace lỗi trong Jaeger (`screenshots/jaeger-error-trace.png`)
- [x] Trang Alerts của Prometheus với ≥ 2 alerts cùng đang **FIRING** (`screenshots/prometheus-alert-firing.png`): `LLMCostBurnRateHigh` (`FIRING`, value `$7.47/giờ`) và `AgentHighErrorRate` (`FIRING`), kèm `AgentHighLatencyP95` ở trạng thái `PENDING`.

**Trả lời câu hỏi Exercise 7.4:**
- **Khoảng cách giữa `avg` và `p95`/`p99`:** Trên đồ thị `Latency /ask`, đường `p50`/`avg`/`p95` nằm sát nhau ở mức ~`190–296 ms`, trong khi đường `p99` tách hẳn lên ~`1.7–1.8s` vì chỉ ~3% request chậm đuôi (`MOCK_SLOW_RATE=0.03`) làm `p99` tăng vọt nhưng chưa đủ kéo `avg` hay `p95` lên cao.
- **Vì sao `input token > output token`:** Với `agent v2`, mỗi câu hỏi đều qua bước retrieval lấy đoạn tài liệu từ `KNOWLEDGE_BASE` ghép vào prompt (`SYSTEM_PROMPT + context + question`), nên độ dài đầu vào lớn hơn câu trả lời ngắn gọn ở đầu ra (vd trong log trace `640dd8d88732bd22b01a6fac72bc08c8`: `input_tokens = 74`, `output_tokens = 37`).
- **Vì sao `/metrics` bị chặn (`404`) ở Nginx:** Trong `nginx/nginx.conf`, `location = /metrics { return 404; }` chặn truy cập từ bên ngoài vì `/metrics` lộ thông số nội bộ (route, lưu lượng, chi phí, số instance). Chỉ Prometheus trong mạng Docker nội bộ `obs_net` mới được scrape trực tiếp `/metrics` của các container `agent`.

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` (`FIRING` trong ảnh `prometheus-alert-firing.png`) | ~1–2 phút (theo rule `for: 1m` + chu kỳ scrape/đánh giá) | `Error rate` và `Requests/s theo status code` (`503`) |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` (`PENDING` trong ảnh `prometheus-alert-firing.png`, chuẩn bị sang `FIRING`) | Theo rule `for: 2m` | `Latency /ask — p50 / p95 / p99` (đường `p95` vọt lên > 1s) |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` (`FIRING` trong ảnh `prometheus-alert-firing.png`, tốc độ `$7.47/giờ > $2/giờ`) | Theo rule `for: 2m` | `Cost burn rate (USD/giờ)` và `LLM latency p95 theo model` |
| D | `docker pause` 1 instance *(phân tích theo `alert_rules.yml` & `nginx.conf`)* | `AgentInstanceDown` (`up{job="agent"} == 0`) | `for: 30s` sau khi `pause` | `Instances up` giảm từ 2 xuống 1; Locust nhận 504 nhưng `Error rate` agent vẫn xanh vì lỗi 504 xảy ra ở Nginx trước khi agent hoàn tất request |
| E | `AGENT_VERSION=v1` *(phân tích)* | **Không có alert nào firing** | Không firing | `Retrieval hit ratio` tụt về 0, `Tokens/s` giảm, bảng `Phiên bản đang chạy` đổi sang `v1` |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Observability hạ tầng (latency, error rate, CPU, RAM) chỉ đo *hệ thống có chạy nhanh và không lỗi 5xx hay không*, chứ không đo *câu trả lời có đúng hay không*. Để phát hiện sự cố tụt chất lượng như chuyển nhầm sang `v1`:
1. Chạy **Eval tự động trên golden dataset** (`eval/run_eval.py`) như một **quality gate trong CI/CD** trước khi deploy để chặn merge/release nếu accuracy giảm.
2. Theo dõi các **metric nghiệp vụ / chất lượng** trong production như `retrieval_hit_ratio` (tỉ lệ tìm thấy context), phản hồi người dùng (thumbs up/down), và chạy **LLM-as-a-judge** định kỳ trên một tỉ lệ mẫu (sampling) traffic thật.

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: `640dd8d88732bd22b01a6fac72bc08c8`
- Tổng thời gian: `3.3s` (`~3300 ms`)
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (`1643.8 ms`, ~49.8% tổng thời gian; span `agent.retrieve_context` chiếm ~1.6s còn lại)
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-25T12:21:36.951667+00:00", "level": "INFO", "service": "observable-agent", "instance": "ea4695487700", "event": "llm_call", "trace_id": "640dd8d88732bd22b01a6fac72bc08c8", "span_id": "f2ef6520f572b63e", "request_id": "bd89d310f3eb", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 74, "output_tokens": 37, "cost_usd": 3.3e-05, "llm_ms": 1643.8}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS (Aggregated) | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 60.70 (POST /ask: 55.17) | 190 | 230 (POST /ask: 240) | 1700 | 61 / 7,809 (0.78%) |
| 3 | 61.13 (POST /ask: 55.51) | 190 | 220 (POST /ask: 230) | 1700 | 79 / 7,863 (1.00%) |

**Giải thích kết quả:** Scale từ 1 lên 3 instance không làm RPS tăng mạnh (`60.70` → `61.13 req/s`) và `p95`/`p99` gần như giữ nguyên (`230` → `220 ms`, `p99 = 1700 ms`). Lý do gồm hai điểm:
1. Locust mô phỏng 100 user có thời gian nghỉ `wait_time = between(0.5, 2)` giây nên tổng tải sinh ra bị giới hạn tự nhiên ở mức ~60 req/s, chưa làm bão hòa 1 worker FastAPI async.
2. Nút thắt thời gian phản hồi nằm ở **độ trễ I/O của upstream LLM** (`MOCK_LATENCY_MS` ~120–180 ms và 3% request chậm đuôi `1500 ms` tạo `p99 = 1700 ms`), nên thêm instance giúp tăng khả năng chịu tải đồng thời cao hơn và chống lỗi đơn điểm (HA), chứ không rút ngắn thời gian xử lý của từng lời gọi LLM.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. **Không dùng average làm SLO:** chỉ cần 3% request chậm đuôi (`MOCK_SLOW_RATE=0.03`) thì `avg` chỉ nhích từ `191 ms` lên `210.7 ms`, trong khi `p99` nhảy vọt lên `1656.3 ms`.
  2. **So sánh phiên bản phải kết hợp cả chất lượng và chi phí trên câu đúng:** `agent v2` dùng gấp ~2 lần token so với `v1` (`114.1` vs `57.0`), nhưng accuracy tăng từ `4.35%` lên `100%`, giúp `cost / câu đúng` rẻ hơn ~11.6 lần.
  3. **3 trụ cột Metrics – Traces – Logs bổ trợ cho nhau:** Grafana báo hiệu triệu chứng (`p95`, `error rate`), Jaeger chỉ ra span gây chậm/lỗi (`chat mock-llm-small` `1643.8 ms`), còn `trace_id` giúp truy thẳng ra dòng log JSON chi tiết; đồng thời vẫn cần eval chất lượng vì alert hạ tầng không bắt được lỗi trả lời sai (`AGENT_VERSION=v1`).
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?
  1. Metric & alert ở tầng **load balancer / synthetic probe bên ngoài** để bắt lỗi `502`/`504` (vì metric nội bộ của agent không nhìn thấy request bị timeout ở Nginx).
  2. Metric chất lượng **RAG & feedback** (tỉ lệ retrieval rỗng, điểm đánh giá tự động / thumbs-down) và cảnh báo **rate-limit 429 / budget 402** theo tenant/API key.
