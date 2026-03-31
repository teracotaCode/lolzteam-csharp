using System;
using System.Net;

namespace Lolzteam.Runtime.Errors;

/// <summary>
/// Exception thrown for server-side errors (5xx).
/// </summary>
public sealed class ServerException : HttpException
{
    public ServerException(HttpStatusCode statusCode, string? responseBody = null)
        : base(statusCode, $"Server error: HTTP {(int)statusCode}", responseBody) { }

    public ServerException(HttpStatusCode statusCode, string message, string? responseBody = null)
        : base(statusCode, message, responseBody) { }
}
