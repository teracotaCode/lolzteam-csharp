using System.Net;

namespace Lolzteam.Runtime;

/// <summary>
/// Handles retry logic with exponential backoff and jitter.
/// </summary>
public sealed class RetryHandler
{
    private readonly RetryConfig _config;
    private readonly Random _random;

    public RetryHandler(RetryConfig? config = null)
    {
        _config = config ?? RetryConfig.Default;
        _random = new Random();
    }

    /// <summary>
    /// Executes an async operation with retry logic.
    /// </summary>
    public async Task<T> ExecuteAsync<T>(
        Func<CancellationToken, Task<T>> operation,
        CancellationToken cancellationToken = default)
    {
        Exception? lastException = null;

        for (int attempt = 0; attempt <= _config.MaxRetries; attempt++)
        {
            try
            {
                return await operation(cancellationToken).ConfigureAwait(false);
            }
            catch (Errors.HttpException ex) when (
                attempt < _config.MaxRetries &&
                _config.RetryableStatusCodes.Contains((int)ex.StatusCode))
            {
                lastException = ex;
                var delay = ComputeDelay(attempt, ex);
                await Task.Delay(delay, cancellationToken).ConfigureAwait(false);
            }
            catch (HttpRequestException ex) when (attempt < _config.MaxRetries)
            {
                lastException = ex;
                var delay = ComputeDelay(attempt, null);
                await Task.Delay(delay, cancellationToken).ConfigureAwait(false);
            }
            catch (TaskCanceledException) when (cancellationToken.IsCancellationRequested)
            {
                throw;
            }
            catch (TaskCanceledException ex) when (attempt < _config.MaxRetries)
            {
                // Timeout — retryable
                lastException = ex;
                var delay = ComputeDelay(attempt, null);
                await Task.Delay(delay, cancellationToken).ConfigureAwait(false);
            }
        }

        throw lastException ?? new InvalidOperationException("Retry exhausted with no exception");
    }

    /// <summary>
    /// Checks if an HTTP status code is retryable according to config.
    /// </summary>
    public bool IsRetryable(HttpStatusCode statusCode)
        => _config.RetryableStatusCodes.Contains((int)statusCode);

    /// <summary>
    /// Computes delay for a given attempt with exponential backoff + jitter.
    /// </summary>
    internal TimeSpan ComputeDelay(int attempt, Errors.HttpException? exception)
    {
        // Honor Retry-After from rate limit exceptions
        if (exception is Errors.RateLimitException rle && rle.RetryAfterSeconds.HasValue)
        {
            return TimeSpan.FromSeconds(rle.RetryAfterSeconds.Value);
        }

        // Exponential backoff
        var baseDelay = _config.InitialDelay.TotalMilliseconds * Math.Pow(_config.Multiplier, attempt);
        baseDelay = Math.Min(baseDelay, _config.MaxDelay.TotalMilliseconds);

        // Jitter
        var jitter = baseDelay * _config.JitterFactor * (2.0 * _random.NextDouble() - 1.0);
        var totalMs = Math.Max(0, baseDelay + jitter);

        return TimeSpan.FromMilliseconds(totalMs);
    }
}
