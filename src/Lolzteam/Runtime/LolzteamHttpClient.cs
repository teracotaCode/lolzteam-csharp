using System.Net;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using Lolzteam.Runtime.Errors;

namespace Lolzteam.Runtime;

/// <summary>
/// Configuration for the Lolzteam HTTP client.
/// </summary>
public sealed record LolzteamClientConfig
{
    /// <summary>Default base URL for the Forum API.</summary>
    public const string DefaultForumBaseUrl = "https://prod-api.lolz.live";

    /// <summary>Default base URL for the Market API.</summary>
    public const string DefaultMarketBaseUrl = "https://prod-api.lzt.market";

    /// <summary>Base URL for the API.</summary>
    public required string BaseUrl { get; init; }

    /// <summary>Bearer token for authentication.</summary>
    public required string Token { get; init; }

    /// <summary>Retry configuration. Null uses defaults.</summary>
    public RetryConfig? RetryConfig { get; init; }

    /// <summary>Rate limit configuration. Null uses defaults.</summary>
    public RateLimitConfig? RateLimitConfig { get; init; }

    /// <summary>Proxy configuration. Null means no proxy.</summary>
    public ProxyConfig? ProxyConfig { get; init; }

    /// <summary>Request timeout. Default 30 seconds.</summary>
    public TimeSpan Timeout { get; init; } = TimeSpan.FromSeconds(30);

    /// <summary>User-Agent string. Default "Lolzteam.NET/1.0".</summary>
    public string UserAgent { get; init; } = "Lolzteam.NET/1.0";
}

/// <summary>
/// HTTP client implementation for Lolzteam API with retry, rate limiting, and proxy support.
/// </summary>
public sealed class LolzteamHttpClient : ILolzteamHttpClient
{
    private readonly HttpClient _httpClient;
    private readonly RetryHandler _retryHandler;
    private readonly RateLimiter _rateLimiter;
    private readonly LolzteamClientConfig _config;
    private readonly bool _ownsHttpClient;
    private bool _disposed;

    private static readonly JsonSerializerOptions s_jsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        PropertyNameCaseInsensitive = true,
        DefaultIgnoreCondition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull
    };

    /// <summary>
    /// Creates a new LolzteamHttpClient with the given configuration.
    /// </summary>
    public LolzteamHttpClient(LolzteamClientConfig config)
    {
        _config = config ?? throw new ArgumentNullException(nameof(config));

        var handler = CreateHandler(config.ProxyConfig);
        _httpClient = new HttpClient(handler, disposeHandler: true)
        {
            BaseAddress = new Uri(config.BaseUrl.TrimEnd('/')),
            Timeout = config.Timeout
        };
        _httpClient.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", config.Token);
        _httpClient.DefaultRequestHeaders.UserAgent.ParseAdd(config.UserAgent);
        _httpClient.DefaultRequestHeaders.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));

        _retryHandler = new RetryHandler(config.RetryConfig);
        _rateLimiter = new RateLimiter(config.RateLimitConfig);
        _ownsHttpClient = true;
    }

    /// <summary>
    /// Creates a new LolzteamHttpClient using an externally-managed HttpClient.
    /// Useful for testing or custom configuration.
    /// </summary>
    public LolzteamHttpClient(
        HttpClient httpClient,
        RetryConfig? retryConfig = null,
        RateLimitConfig? rateLimitConfig = null)
    {
        _httpClient = httpClient ?? throw new ArgumentNullException(nameof(httpClient));
        _config = new LolzteamClientConfig
        {
            BaseUrl = httpClient.BaseAddress?.ToString() ?? "https://prod-api.lzt.market",
            Token = ""
        };
        _retryHandler = new RetryHandler(retryConfig);
        _rateLimiter = new RateLimiter(rateLimitConfig);
        _ownsHttpClient = false;
    }

    /// <inheritdoc />
    public async Task<JsonElement> RequestAsync(
        HttpMethod method,
        string path,
        Dictionary<string, string>? queryParams = null,
        object? body = null,
        CancellationToken cancellationToken = default)
    {
        return await _retryHandler.ExecuteAsync(async ct =>
        {
            await _rateLimiter.AcquireAsync(ct).ConfigureAwait(false);

            var url = BuildUrl(path, queryParams);
            using var request = new HttpRequestMessage(method, url);

            if (body != null)
            {
                var json = JsonSerializer.Serialize(body, s_jsonOptions);
                request.Content = new StringContent(json, Encoding.UTF8, "application/json");
            }

            return await SendAndParseAsync(request, ct).ConfigureAwait(false);
        }, cancellationToken).ConfigureAwait(false);
    }

    /// <inheritdoc />
    public async Task<JsonElement> RequestMultipartAsync(
        HttpMethod method,
        string path,
        Dictionary<string, string>? queryParams = null,
        Dictionary<string, string>? formFields = null,
        Dictionary<string, (string FileName, byte[] Content)>? fileFields = null,
        CancellationToken cancellationToken = default)
    {
        return await _retryHandler.ExecuteAsync(async ct =>
        {
            await _rateLimiter.AcquireAsync(ct).ConfigureAwait(false);

            var url = BuildUrl(path, queryParams);
            using var request = new HttpRequestMessage(method, url);

            var multipart = new MultipartFormDataContent();

            if (formFields != null)
            {
                foreach (var (key, value) in formFields)
                {
                    if (value != null)
                        multipart.Add(new StringContent(value), key);
                }
            }

            if (fileFields != null)
            {
                foreach (var (fieldName, (fileName, content)) in fileFields)
                {
                    var fileContent = new ByteArrayContent(content);
                    fileContent.Headers.ContentType = new MediaTypeHeaderValue("application/octet-stream");
                    multipart.Add(fileContent, fieldName, fileName);
                }
            }

            request.Content = multipart;

            return await SendAndParseAsync(request, ct).ConfigureAwait(false);
        }, cancellationToken).ConfigureAwait(false);
    }

    private async Task<JsonElement> SendAndParseAsync(HttpRequestMessage request, CancellationToken ct)
    {
        using var response = await _httpClient.SendAsync(request, ct).ConfigureAwait(false);
        var responseBody = await response.Content.ReadAsStringAsync(ct).ConfigureAwait(false);

        if (!response.IsSuccessStatusCode)
        {
            ThrowForStatus(response.StatusCode, responseBody, response);
        }

        if (string.IsNullOrWhiteSpace(responseBody))
        {
            return new JsonElement();
        }

        using var doc = JsonDocument.Parse(responseBody);
        return doc.RootElement.Clone();
    }

    private static string BuildUrl(string path, Dictionary<string, string>? queryParams)
    {
        if (queryParams == null || queryParams.Count == 0)
            return path;

        var sb = new StringBuilder(path);
        var first = !path.Contains('?');
        foreach (var (key, value) in queryParams)
        {
            if (string.IsNullOrEmpty(value)) continue;
            sb.Append(first ? '?' : '&');
            sb.Append(Uri.EscapeDataString(key));
            sb.Append('=');
            sb.Append(Uri.EscapeDataString(value));
            first = false;
        }
        return sb.ToString();
    }

    private static void ThrowForStatus(HttpStatusCode statusCode, string responseBody, HttpResponseMessage response)
    {
        switch ((int)statusCode)
        {
            case 401:
            case 403:
                throw new AuthException(statusCode, responseBody);
            case 404:
                throw new NotFoundException(responseBody);
            case 429:
                double? retryAfter = null;
                if (response.Headers.TryGetValues("Retry-After", out var values))
                {
                    var val = values.FirstOrDefault();
                    if (val != null && double.TryParse(val, out var seconds))
                        retryAfter = seconds;
                }
                throw new RateLimitException(retryAfter, responseBody);
            case >= 500:
                throw new ServerException(statusCode, responseBody);
            default:
                throw new HttpException(statusCode, responseBody);
        }
    }

    private static HttpMessageHandler CreateHandler(ProxyConfig? proxyConfig)
    {
        var handler = new HttpClientHandler
        {
            AutomaticDecompression = DecompressionMethods.GZip | DecompressionMethods.Deflate
        };

        if (proxyConfig != null)
        {
            proxyConfig.Validate();
            handler.Proxy = proxyConfig.ToWebProxy();
            handler.UseProxy = true;
        }

        return handler;
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        _rateLimiter.Dispose();
        if (_ownsHttpClient)
            _httpClient.Dispose();
    }
}
