from limiter import RateLimiter

rl = RateLimiter(capacity=5, rate=2)  # bursts of 5, then 2 requests/second
for i in range(7):
    print(i, rl.allow("alice"))
print("retry after", rl.retry_after("alice"))
