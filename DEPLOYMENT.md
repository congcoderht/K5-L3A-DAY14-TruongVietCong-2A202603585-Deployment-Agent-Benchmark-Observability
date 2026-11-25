# Deployment Information

## Public URL
https://prolific-unity-production-0b2b91ea.up.railway.app

## Platform
Railway (Docker service `prolific-unity` + managed `Redis`, Root Directory: `/06-lab-complete`)

## Test Commands

### Health Check
```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://prolific-unity-production-0b2b91ea.up.railway.app/health
# Expected: 200
```

### Readiness Check (Redis connection)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://prolific-unity-production-0b2b91ea.up.railway.app/ready
# Expected: 200
```

### API Test (Authentication required → 401)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' \
  -X POST https://prolific-unity-production-0b2b91ea.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
# Expected: 401
```

### API Test (With valid `X-API-Key` → 200)
```bash
curl -X POST https://prolific-unity-production-0b2b91ea.up.railway.app/ask \
  -H "X-API-Key: <YOUR_AGENT_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "Hello"}'
# Expected: 200
```

## Environment Variables Set
- `PORT` (injected by Railway: `8080`, Target Port configured to `8080`)
- `ENVIRONMENT` (`production`)
- `AGENT_API_KEY` (configured securely in Railway Variables)
- `REDIS_URL` (internal reference to Railway Redis service)
- `RATE_LIMIT_PER_MINUTE` (`10`)
- `DAILY_BUDGET_USD` (`1.0`)
- `MONTHLY_BUDGET_USD` (`10.0`)

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
