const defaultHeaders = {
  "Content-Type": "application/json"
};

export async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: defaultHeaders,
    ...options
  });

  if (!response.ok) {
    const message = await readError(response);
    throw new Error(message);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

async function readError(response) {
  const text = await response.text();
  if (!text) {
    return `${response.status} ${response.statusText}`;
  }

  try {
    const payload = JSON.parse(text);
    return payload.detail || text;
  } catch {
    return text;
  }
}

export function jsonOptions(method, body) {
  return {
    method,
    body: JSON.stringify(body)
  };
}
