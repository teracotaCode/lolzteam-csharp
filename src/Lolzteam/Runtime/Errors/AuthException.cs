using System;
using System.Net;

namespace Lolzteam.Runtime.Errors;

/// <summary>
/// Exception thrown for authentication/authorization failures (401, 403).
/// </summary>
public sealed class AuthException : HttpException
{
    public AuthException(HttpStatusCode statusCode, string? responseBody = null)
        : base(statusCode, $"Authentication failed: HTTP {(int)statusCode}", responseBody ?? string.Empty)
    {
    }

    public AuthException(string message)
        : base(HttpStatusCode.Unauthorized, message, string.Empty) { }

    public AuthException(string message, Exception innerException)
        : base(HttpStatusCode.Unauthorized, message, innerException) { }
}
