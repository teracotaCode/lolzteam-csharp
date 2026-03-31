using System;
using System.Net;

namespace Lolzteam.Runtime.Errors;

/// <summary>
/// Exception thrown when rate limited (HTTP 429).
/// </summary>
public sealed class RateLimitException : HttpException
{
    /// <summary>Seconds until the rate limit resets, if provided by the server.</summary>
    public double? RetryAfterSeconds { get; }

    public RateLimitException(double? retryAfterSeconds = null, string? responseBody = null)
        : base(HttpStatusCode.TooManyRequests, "Rate limit exceeded", responseBody)
    {
        RetryAfterSeconds = retryAfterSeconds;
    }

    public RateLimitException(string message, double? retryAfterSeconds = null)
        : base(HttpStatusCode.TooManyRequests, message)
    {
        RetryAfterSeconds = retryAfterSeconds;
    }
}
