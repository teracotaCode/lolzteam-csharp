namespace Lolzteam.Runtime;

/// <summary>
/// Token bucket rate limiter for client-side request throttling.
/// Thread-safe.
/// </summary>
public sealed class RateLimiter : IDisposable
{
    private readonly RateLimitConfig _config;
    private readonly SemaphoreSlim _semaphore = new(1, 1);
    private double _tokens;
    private DateTime _lastRefill;
    private bool _disposed;

    public RateLimiter(RateLimitConfig? config = null)
    {
        _config = config ?? RateLimitConfig.Default;
        _tokens = _config.MaxTokens;
        _lastRefill = DateTime.UtcNow;
    }

    /// <summary>
    /// Acquires a token, waiting if necessary until one is available.
    /// </summary>
    public async Task AcquireAsync(CancellationToken cancellationToken = default)
    {
        while (true)
        {
            cancellationToken.ThrowIfCancellationRequested();

            await _semaphore.WaitAsync(cancellationToken).ConfigureAwait(false);
            var released = false;
            try
            {
                Refill();

                if (_tokens >= 1.0)
                {
                    _tokens -= 1.0;
                    return;
                }

                // Calculate wait time until next token
                var tokensNeeded = 1.0 - _tokens;
                var waitMs = (tokensNeeded / _config.RefillAmount) * _config.RefillPeriod.TotalMilliseconds;
                var waitTime = TimeSpan.FromMilliseconds(Math.Max(1, waitMs));

                // Release lock before waiting so others aren't blocked
                _semaphore.Release();
                released = true;
                await Task.Delay(waitTime, cancellationToken).ConfigureAwait(false);
                continue; // Re-acquire and retry
            }
            finally
            {
                if (!released)
                    _semaphore.Release();
            }
        }
    }

    /// <summary>
    /// Returns the current number of available tokens (approximate).
    /// </summary>
    public double AvailableTokens
    {
        get
        {
            _semaphore.Wait();
            try
            {
                Refill();
                return _tokens;
            }
            finally
            {
                _semaphore.Release();
            }
        }
    }

    private void Refill()
    {
        var now = DateTime.UtcNow;
        var elapsed = now - _lastRefill;
        if (elapsed <= TimeSpan.Zero) return;

        var periodsElapsed = elapsed.TotalMilliseconds / _config.RefillPeriod.TotalMilliseconds;
        var tokensToAdd = periodsElapsed * _config.RefillAmount;
        _tokens = Math.Min(_config.MaxTokens, _tokens + tokensToAdd);
        _lastRefill = now;
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        _semaphore.Dispose();
    }
}
