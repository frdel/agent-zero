/**
 * Call a JSON-in JSON-out API endpoint
 * Data is automatically serialized
 * @param {string} endpoint - The API endpoint to call
 * @param {any} data - The data to send to the API
 * @returns {Promise<any>} The JSON response from the API
 */
export async function callJsonApi(endpoint, data) {
  // Check if API calls are paused due to authentication failure
  if (window.isApiCallsPaused && window.isApiCallsPaused()) {
    throw new Error("AUTH_PAUSED");
  }

  const response = await fetchApi(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "same-origin",
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(error);
  }
  const jsonResponse = await response.json();
  return jsonResponse;
}

/**
 * Fetch wrapper for A0 APIs that ensures token exchange
 * Automatically adds CSRF token to request headers
 * @param {string} url - The URL to fetch
 * @param {Object} [request] - The fetch request options
 * @returns {Promise<Response>} The fetch response
 */
export async function fetchApi(url, request) {
  // Check if API calls are paused due to authentication failure
  if (window.isApiCallsPaused && window.isApiCallsPaused()) {
    throw new Error("AUTH_PAUSED");
  }

  async function _wrap(retry) {
    // get the CSRF token
    const token = await getCsrfToken();

    // create a new request object if none was provided
    const finalRequest = request || {};

    // ensure headers object exists
    finalRequest.headers = finalRequest.headers || {};

    // add the CSRF token to the headers
    finalRequest.headers["X-CSRF-Token"] = token;

    // perform the fetch with the updated request
    const response = await fetch(url, finalRequest);

    // check if there was an CSRF error
    if (response.status === 403 && retry) {
      // retry the request with new token
      csrfToken = null;
      return await _wrap(false);
    }

    // return the response
    return response;
  }

  // perform the request
  const response = await _wrap(true);

  // return the response
  return response;
}

// csrf token stored locally
let csrfToken = null;

// Global function to clear CSRF token (called after authentication)
globalThis.clearCsrfToken = function() {
  csrfToken = null;
  // Also clear any CSRF cookies that might be cached
  try {
    // Clear all cookies that start with csrf_token_
    document.cookie.split(";").forEach(function(c) {
      const cookie = c.trim();
      if (cookie.startsWith('csrf_token_')) {
        const eqPos = cookie.indexOf("=");
        const name = eqPos > -1 ? cookie.substr(0, eqPos) : cookie;
        document.cookie = name + "=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/";
      }
    });
  } catch (e) {
    console.warn('Failed to clear CSRF cookies:', e);
  }
};

/**
 * Get the CSRF token for API requests
 * Caches the token after first request
 * @returns {Promise<string>} The CSRF token
 */
async function getCsrfToken() {
  // Don't request CSRF token if API calls are paused
  if (window.isApiCallsPaused && window.isApiCallsPaused()) {
    throw new Error("AUTH_PAUSED");
  }

  if (csrfToken) return csrfToken;
  const response = await fetch("/csrf_token", {
    credentials: "same-origin",
  }).then((r) => r.json());
  csrfToken = response.token;
  document.cookie = `csrf_token_${response.runtime_id}=${csrfToken}; SameSite=Strict; Path=/`;
  return csrfToken;
}
