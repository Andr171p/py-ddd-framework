-- KEYS[1] = bucket key
-- ARGV[1] = lease_id
-- ARGV[2] = limit
-- ARGV[3] = lease_ttl_ms
--
-- Return: 1 = acquired, 0 = limit reached

local key = KEYS[1]
local lease_id = ARGV[1]
local limit = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])

local time = redis.call("TIME")
local now = tonumber(time[1]) * 1000 + math.floor(tonumber(time[2]) / 1000)

-- Удаляем истёкшие аренды.
redis.call("ZREMRANGEBYSCORE", key, "-inf", now)

-- Идемпотентный повтор с тем же lease_id.
if redis.call("ZSCORE", key, lease_id) then
    return 1
end

if redis.call("ZCARD", key) >= limit then
    return 0
end

redis.call("ZADD", key, now + ttl, lease_id)

-- Redis-ключ должен жить не меньше самой долгой аренды.
local latest = redis.call("ZREVRANGE", key, 0, 0, "WITHSCORES")

local key_ttl = math.max(1, math.ceil(tonumber(latest[2]) - now + 1000))

redis.call("PEXPIRE", key, key_ttl)

return 1