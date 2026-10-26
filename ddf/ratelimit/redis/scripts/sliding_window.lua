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
    "window_id", "current", "previous"
)

local stored_window = tonumber(state[1])
local current = tonumber(state[2]) or 0
local previous = tonumber(state[3]) or 0

-- Advance window counters.
if not stored_window then
    current = 0
    previous = 0
elseif window_id > stored_window then
    if window_id == stored_window + 1 then
        previous = current
    else
        previous = 0
    end

    current = 0
elseif window_id < stored_window then
    -- Avoid resetting counters if the clock moves backward.
    window_id = stored_window
    elapsed = 0
end

-- Weight of the previous window.
local weight = (window_ms - elapsed) / window_ms
local estimated = current + previous * weight

local allowed = 0
local retry_ms = 0

if estimated + cost <= limit then
    current = current + cost
    allowed = 1
    estimated = estimated + cost
else
    if previous > 0 and current + cost <= limit then
        -- The previous window's contribution will decay
        -- enough during the current window.
        local excess = estimated + cost - limit

        retry_ms = math.ceil(
            excess * window_ms / previous
        )
    else
        -- The current counter is too large.
        -- Wait for the next window and its subsequent decay.
        local until_next = window_ms - elapsed

        local decay_ms = 0
        if current > 0 then
            decay_ms = math.ceil(
                window_ms * math.max(
                    0,
                    1 - (limit - cost) / current
                )
            )
        end

        retry_ms = until_next + decay_ms
    end

    retry_ms = math.max(1, retry_ms)
end

redis.call(
    "HSET", key,
    "window_id", window_id,
    "current", current,
    "previous", previous
)

redis.call("PEXPIRE", key, 2 * window_ms + 1)

return {
    allowed,
    math.max(0, math.floor(limit - estimated)),
    retry_ms
}

