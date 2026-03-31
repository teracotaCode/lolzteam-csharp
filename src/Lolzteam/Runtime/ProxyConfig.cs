using System;
using System.Net;
using Lolzteam.Runtime.Errors;

namespace Lolzteam.Runtime;

/// <summary>
/// Supported proxy protocols.
/// </summary>
public enum ProxyProtocol
{
    Http,
    Https,
    Socks5
}

/// <summary>
/// Configuration for proxy connections.
/// </summary>
public sealed record ProxyConfig
{
    /// <summary>Proxy protocol.</summary>
    public ProxyProtocol Protocol { get; init; } = ProxyProtocol.Http;

    /// <summary>Proxy hostname or IP.</summary>
    public required string Host { get; init; }

    /// <summary>Proxy port.</summary>
    public required int Port { get; init; }

    /// <summary>Optional proxy username.</summary>
    public string? Username { get; init; }

    /// <summary>Optional proxy password.</summary>
    public string? Password { get; init; }

    /// <summary>
    /// Validates the proxy configuration.
    /// </summary>
    /// <exception cref="ValidationException">Thrown when the configuration is invalid.</exception>
    public void Validate()
    {
        if (string.IsNullOrWhiteSpace(Host))
            throw new ValidationException("Proxy host cannot be empty.");

        if (Port < 1 || Port > 65535)
            throw new ValidationException($"Proxy port must be between 1 and 65535, got {Port}.");

        // Validate host is not just whitespace or contains invalid chars
        if (Host.Contains(' '))
            throw new ValidationException($"Proxy host contains invalid characters: '{Host}'.");

        // If username is provided, password should be too (and vice versa)
        if (!string.IsNullOrEmpty(Username) && string.IsNullOrEmpty(Password))
            throw new ValidationException("Proxy password is required when username is set.");

        if (string.IsNullOrEmpty(Username) && !string.IsNullOrEmpty(Password))
            throw new ValidationException("Proxy username is required when password is set.");
    }

    /// <summary>
    /// Gets the proxy URI string.
    /// </summary>
    public Uri ToUri()
    {
        var scheme = Protocol switch
        {
            ProxyProtocol.Http => "http",
            ProxyProtocol.Https => "https",
            ProxyProtocol.Socks5 => "socks5",
            _ => throw new ValidationException($"Unsupported proxy protocol: {Protocol}")
        };

        if (!string.IsNullOrEmpty(Username))
        {
            return new Uri($"{scheme}://{Uri.EscapeDataString(Username)}:{Uri.EscapeDataString(Password!)}@{Host}:{Port}");
        }

        return new Uri($"{scheme}://{Host}:{Port}");
    }

    /// <summary>
    /// Creates an IWebProxy instance for use with HttpClient.
    /// </summary>
    public IWebProxy ToWebProxy()
    {
        Validate();
        var proxy = new WebProxy(ToUri())
        {
            BypassProxyOnLocal = false
        };

        if (!string.IsNullOrEmpty(Username))
        {
            proxy.Credentials = new NetworkCredential(Username, Password);
        }

        return proxy;
    }

    /// <summary>
    /// Parses a proxy URL string into a ProxyConfig.
    /// Supported formats: protocol://host:port, protocol://user:pass@host:port
    /// </summary>
    public static ProxyConfig Parse(string proxyUrl)
    {
        if (string.IsNullOrWhiteSpace(proxyUrl))
            throw new ValidationException("Proxy URL cannot be empty.");

        try
        {
            var uri = new Uri(proxyUrl);
            var protocol = uri.Scheme.ToLowerInvariant() switch
            {
                "http" => ProxyProtocol.Http,
                "https" => ProxyProtocol.Https,
                "socks5" => ProxyProtocol.Socks5,
                _ => throw new ValidationException($"Unsupported proxy scheme: {uri.Scheme}")
            };

            var config = new ProxyConfig
            {
                Protocol = protocol,
                Host = uri.Host,
                Port = uri.Port > 0 ? uri.Port : throw new ValidationException("Proxy port is required."),
                Username = string.IsNullOrEmpty(uri.UserInfo) ? null : Uri.UnescapeDataString(uri.UserInfo.Split(':')[0]),
                Password = uri.UserInfo?.Contains(':') == true ? Uri.UnescapeDataString(uri.UserInfo.Split(':', 2)[1]) : null
            };

            config.Validate();
            return config;
        }
        catch (UriFormatException ex)
        {
            throw new ValidationException($"Invalid proxy URL: {proxyUrl}", ex);
        }
    }
}
