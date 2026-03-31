namespace Lolzteam.Runtime;

/// <summary>
/// Configuration for client-side rate limiting using a token bucket algorithm.
/// </summary>
public sealed record RateLimitConfig
{
    /// <summary>Maximum number of tokens in the bucket. Default 3.</summary>
    public int MaxTokens { get; init; } = 3;

    /// <summary>Time period for token replenishment. Default 1 second.</summary>
    public TimeSpan RefillPeriod { get; init; } = TimeSpan.FromSeconds(1);

    /// <summary>Number of tokens added per refill period. Default 3.</summary>
    public int RefillAmount { get; init; } = 3;

    /// <summary>Default rate limit (3 requests/second for Lolzteam API).</summary>
    public static RateLimitConfig Default => new();

    /// <summary>No rate limiting.</summary>
    public static RateLimitConfig None => new() { MaxTokens = int.MaxValue, RefillAmount = int.MaxValue };
}
