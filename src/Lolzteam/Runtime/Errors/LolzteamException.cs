using System;

namespace Lolzteam.Runtime.Errors;

/// <summary>
/// Base exception for all Lolzteam API errors.
/// </summary>
public class LolzteamException : Exception
{
    public LolzteamException() { }
    public LolzteamException(string message) : base(message) { }
    public LolzteamException(string message, Exception innerException) : base(message, innerException) { }
}
