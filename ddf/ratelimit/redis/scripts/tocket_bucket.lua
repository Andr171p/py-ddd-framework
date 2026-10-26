-- KEYS[1] - Redis key
--
-- ARGV[1] - capacity
-- ARGV[2] - refill_rate (tokens/ms)
-- ARGV[3] - cost
-- ARGV[4] - ttl_ms

local key = KEYS[1]

local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local cost = tonumber(ARGV[3])
local ttl_ms = tonumber(ARGV[4])

local time = redis.call("TIME")
local now = tonumber(time[1]) * 1000 + math.floor(tonumber(time[2]) / 1000)

local state = redis.call("HMGET", key, "tokens", "updated_at")

local tokens = tonumber(state[1]) or capacity
local updated_at = tonumber(state[2]) or now

-- Refill tokens since the last request.
local elapsed = math.max(0, now - updated_at)
tokens = math.min(capacity, tokens + elapsed * refill_rate)

local allowed = 0
local retry_ms = 0

if tokens >= cost then
    tokens = tokens - cost
    allowed = 1
else
    retry_ms = math.max(
        1,
        math.ceil((cost - tokens) / refill_rate)
    )
end

redis.call(
    "HSET", key,
    "tokens", string.format("%.17g", tokens),
    "updated_at", math.max(now, updated_at)
)
redis.call("PEXPIRE", key, ttl_ms)

return {
    allowed,
    math.floor(tokens),
    retry_ms
}
