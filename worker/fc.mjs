import callback from './index.js';

// FC 3.0 HTTP triggers wrap the HTTP request in an event object.
export async function handler(event) {
  const input = JSON.parse(event.toString());
  const method = input.requestContext.http.method;
  const body = input.isBase64Encoded
    ? Buffer.from(input.body || '', 'base64')
    : input.body;
  const request = new Request('https://callback.local' + (input.rawPath || '/'), {
    method,
    headers: input.headers,
    ...(method === 'GET' || method === 'HEAD' ? {} : { body }),
  });
  const response = await callback.fetch(request, process.env);
  return {
    statusCode: response.status,
    headers: Object.fromEntries(response.headers),
    body: await response.text(),
    isBase64Encoded: false,
  };
}
