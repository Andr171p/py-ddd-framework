-- KEYS[1] = bucket key
-- ARGV[1] = lease_id
-- ARGV[2] = lease_ttl_ms
--
-- Return: 1 = renewed, 0 = lease lost

local key = KEYS[1]
local lease_id = ARGV[1]
local ttl = tonumber(ARGV[2])

local time = redis.call("TIME")
local now = tonumber(time[1]) * 1000 + math.floor(tonumber(time[2]) / 1000)

local expires_at = redis.call("ZSCORE", key, lease_id)

if not expires_at then
    return 0
end

-- Истёкший lease нельзя воскресить через renew.
if tonumber(expires_at) <= now then
    redis.call("ZREM", key, lease_id)
    return 0
end

redis.call("ZADD", key, "XX", now + ttl, lease_id)

local latest = redis.call("ZREVRANGE", key, 0, 0, "WITHSCORES")

local key_ttl = math.max(1, math.ceil(tonumber(latest[2]) - now + 1000))

redis.call("PEXPIRE", key, key_ttl)

return 1