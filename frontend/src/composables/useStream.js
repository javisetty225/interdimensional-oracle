/**
 * SSE stream reader.
 * Single responsibility: read a streaming response
 * and emit parsed chunks one by one.
 */
export function useStream() {

  async function* readStream(response) {
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop()

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          yield JSON.parse(line.slice(6))
        } catch {
          // ignore malformed chunks
        }
      }
    }
  }

  return { readStream }
}