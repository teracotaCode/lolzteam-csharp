using System;
using System.Net;

namespace Lolzteam.Runtime.Errors;

/// <summary>
/// Exception thrown when the API returns an HTTP error.
/// </summary>
public class HttpException : LolzteamException
{
    /// <summary>HTTP status code returned by the server.</summary>
    public HttpStatusCode StatusCode { get; }

    /// <summary>Raw response body, if available.</summary>
    public string? ResponseBody { get; }

    public HttpException(HttpStatusCode statusCode, string? responseBody = null)
        : base($"HTTP {(int)statusCode}: {statusCode}")
    {
        StatusCode = statusCode;
        ResponseBody = responseBody;
    }

    public HttpException(HttpStatusCode statusCode, string message, string? responseBody)
        : base(message)
    {
        StatusCode = statusCode;
        ResponseBody = responseBody;
    }

    public HttpException(HttpStatusCode statusCode, string message, Exception innerException)
        : base(message, innerException)
    {
        StatusCode = statusCode;
    }
}
