using System;
using System.Net;

namespace Lolzteam.Runtime.Errors;

/// <summary>
/// Exception thrown when a requested resource is not found (HTTP 404).
/// </summary>
public sealed class NotFoundException : HttpException
{
    public NotFoundException(string? responseBody = null)
        : base(HttpStatusCode.NotFound, "Resource not found", responseBody) { }

    public NotFoundException(string message, string? responseBody = null)
        : base(HttpStatusCode.NotFound, message, responseBody) { }
}
