using System;

namespace Lolzteam.Runtime.Errors;

/// <summary>
/// Exception thrown when request validation fails (bad parameters, invalid config).
/// </summary>
public sealed class ValidationException : LolzteamException
{
    public ValidationException(string message) : base(message) { }
    public ValidationException(string message, Exception innerException) : base(message, innerException) { }
}
