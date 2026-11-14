-- KEYS[1] = bucket key
-- ARGV[1] = lease_id
--
-- Return: 1 = removed, 0 = already absent

local key = KEYS[1]
local lease_id = ARGV[1]

local removed = redis.call("ZREM", key, lease_id)

if removed == 0 then
    return 0
end

local latest = redis.call("ZREVRANGE", key, 0, 0, "WITHSCORES")

if #latest == 0 then
    redis.call("DEL", key)
    return 1
end

local time = redis.call("TIME")
local now = tonumber(time[1]) * 1000 + math.floor(tonumber(time[2]) / 1000)

local key_ttl = math.ceil(tonumber(latest[2]) - now + 1000)

if key_ttl <= 0 then
    redis.call("DEL", key)
else
    redis.call("PEXPIRE", key, key_ttl)
end

return 1