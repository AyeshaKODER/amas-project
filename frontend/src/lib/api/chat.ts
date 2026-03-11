// ---------------------------------------------------------------------------
// Chat service – send messages to agents via FastAPI
// ---------------------------------------------------------------------------

import * as http from './http';
import type { ChatResponse } from './types';

/**
 * Send a chat message to a specific agent.
 *
 * Endpoint: POST /agents/{agentId}/chat
 * Body:     { message, session_id? }
 * Returns:  { reply, session_id }
 */
export async function sendMessage(
  agentId: string,
  message: string,
  sessionId?: string,
): Promise<ChatResponse> {
  return http.post<ChatResponse>(`/agents/${agentId}/chat`, {
    message,
    session_id: sessionId,
  });
}
