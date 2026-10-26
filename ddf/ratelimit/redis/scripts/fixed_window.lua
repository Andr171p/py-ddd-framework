-- KEYS[1] - Redis key
--
-- ARGV[1] - limit
-- ARGV[2] - window_ms
-- ARGV[3] - cost


local key = KEYS[1]

local limit = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local cost = tonumber(ARGV[3])

local time = redis.call("TIME")
local now = tonumber(time[1]) * 1000 + math.floor(tonumber(time[2]) / 1000)

local window_id = math.floor(now / window_ms)
local elapsed = now % window_ms

local state = redis.call(
    "HMGET", key,
    "window_id", "count"
)

local stored_window = tonumber(state[1])
local count = tonumber(state[2]) or 0

-- Reset counter when entering a new window.
if stored_window and window_id < stored_window then
    window_id = stored_window
    elapsed = 0
elseif stored_window ~= window_id then
    count = 0
end

local allowed = 0
local retry_ms = 0

if count + cost <= limit then
    count = count + cost
    allowed = 1
else
    retry_ms = window_ms - elapsed
end

redis.call(
    "HSET", key,
    "window_id", window_id,
    "count", count
)

-- State becomes irrelevant at the next window.
redis.call("PEXPIRE", key, window_ms - elapsed)

return {
    allowed,
    math.max(0, limit - count),
    retry_ms
}
