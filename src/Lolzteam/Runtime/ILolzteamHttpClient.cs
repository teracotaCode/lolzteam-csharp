using System.Text.Json;

namespace Lolzteam.Runtime;

/// <summary>
/// Interface for making HTTP requests to Lolzteam API.
/// </summary>
public interface ILolzteamHttpClient : IDisposable
{
    /// <summary>
    /// Sends an HTTP request and returns the JSON response.
    /// </summary>
    /// <param name="method">HTTP method (GET, POST, PUT, DELETE, PATCH).</param>
    /// <param name="path">API path (relative to base URL).</param>
    /// <param name="queryParams">Optional query string parameters.</param>
    /// <param name="body">Optional request body (will be serialized to JSON).</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>Parsed JSON response as JsonElement.</returns>
    Task<JsonElement> RequestAsync(
        HttpMethod method,
        string path,
        Dictionary<string, string>? queryParams = null,
        object? body = null,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Sends a multipart/form-data HTTP request and returns the JSON response.
    /// </summary>
    /// <param name="method">HTTP method (typically POST).</param>
    /// <param name="path">API path (relative to base URL).</param>
    /// <param name="queryParams">Optional query string parameters.</param>
    /// <param name="formFields">String form fields to include.</param>
    /// <param name="fileFields">Binary file fields (name → (fileName, content)).</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>Parsed JSON response as JsonElement.</returns>
    Task<JsonElement> RequestMultipartAsync(
        HttpMethod method,
        string path,
        Dictionary<string, string>? queryParams = null,
        Dictionary<string, string>? formFields = null,
        Dictionary<string, (string FileName, byte[] Content)>? fileFields = null,
        CancellationToken cancellationToken = default);
}
