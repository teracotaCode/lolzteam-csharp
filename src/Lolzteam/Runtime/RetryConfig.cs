namespace Lolzteam.Runtime;

/// <summary>
/// Configuration for retry behavior on transient failures.
/// </summary>
public sealed record RetryConfig
{
    /// <summary>Maximum number of retry attempts. Default 3.</summary>
    public int MaxRetries { get; init; } = 3;

    /// <summary>Initial delay before first retry. Default 1 second.</summary>
    public TimeSpan InitialDelay { get; init; } = TimeSpan.FromSeconds(1);

    /// <summary>Maximum delay between retries. Default 30 seconds.</summary>
    public TimeSpan MaxDelay { get; init; } = TimeSpan.FromSeconds(30);

    /// <summary>Exponential backoff multiplier. Default 2.0.</summary>
    public double Multiplier { get; init; } = 2.0;

    /// <summary>Maximum jitter factor (0-1). Default 0.25 (25% of delay).</summary>
    public double JitterFactor { get; init; } = 0.25;

    /// <summary>HTTP status codes that trigger retry. Default: 429, 502, 503, 504.</summary>
    public IReadOnlySet<int> RetryableStatusCodes { get; init; } =
        new HashSet<int> { 429, 502, 503, 504 };

    /// <summary>Default retry configuration.</summary>
    public static RetryConfig Default => new();

    /// <summary>No retries.</summary>
    public static RetryConfig None => new() { MaxRetries = 0 };
}
