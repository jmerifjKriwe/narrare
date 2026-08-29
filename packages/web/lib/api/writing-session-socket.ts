/**
 * WebSocket transport for interactive writing sessions.
 *
 * Extracted from `generation.ts` (RULE-06): the interactive-session transport
 * is a deliberately separate lifecycle from the SSE operation path
 * (ADR-052 Session Stop and WebSocket Recovery / ADR-043 Review-Trigger #1),
 * so its symbols must not live inside the SSE barrel — otherwise consumers
 * that import the socket class trip the `check_1_use_ai_operation` SSE-module
 * pattern even though they never touch the SSE surface.
 *
 * Consumers may still re-export these symbols from `generation.ts` for
 * backward compatibility.
 */

// ---------------------------------------------------------------------------
// Server-sent message types
// ---------------------------------------------------------------------------

/** Server-sent message types during an interactive writing session. */
export type StreamStatus = "idle" | "streaming" | "stopped" | "completed" | "failed";

export type StopReason = "user_stop" | "already_idle" | "not_found";

export type RecoveryFailureReason =
  | "session_not_found"
  | "session_expired"
  | "ownership_mismatch"
  | "session_ended";

export interface SessionTranscriptTailItem {
  readonly role: "user" | "assistant" | "system";
  readonly content?: string;
  readonly prose?: string;
}

export interface SessionResponse {
  type:
    | "greeting"
    | "interview_greeting"
    | "text_chunk"
    | "text_done"
    | "draft_done"
    | "feedback_acknowledged"
    | "generation_stopped"
    | "session_recovered"
    | "recovery_failed"
    | "connection_lost"
    | "saved"
    | "timeout"
    | "error";
  text?: string;
  message?: string;
  session_id?: string;
  invocation_id?: string;
  partial_prose?: string;
  sequence?: number;
  reason?: StopReason | RecoveryFailureReason | "idle_timeout" | "server_shutdown";
  stream_status?: StreamStatus;
  transcript_tail?: SessionTranscriptTailItem[];
  recoverable_until?: number;
}

// ---------------------------------------------------------------------------
// Socket configuration
// ---------------------------------------------------------------------------

/** Configuration options for WritingSessionSocket. */
export interface WritingSessionSocketOptions {
  /** Maximum reconnection attempts. Default: 5. */
  readonly maxReconnectAttempts?: number;
  /** Base delay in ms for linear reconnect backoff (delay = base × attempt). Default: 1000. */
  readonly reconnectBaseDelayMs?: number;
}

/** Default values for socket configuration. */
export const DEFAULT_MAX_RECONNECT_ATTEMPTS = 5;
export const DEFAULT_RECONNECT_BASE_DELAY_MS = 1000;

// ---------------------------------------------------------------------------
// WritingSessionSocket
// ---------------------------------------------------------------------------

/**
 * WebSocket wrapper for interactive writing sessions.
 *
 * Connects to `ws(s)://{host}/api/v1/writing/sessions/{chapterId}` and
 * handles reconnection up to maxReconnectAttempts. Gracefully degrades
 * when WebSocket is unavailable (e.g. test environments).
 *
 * Authentication (ADR-084): the handshake presents a single-use, 60 s
 * ticket from `POST /auth/ws-ticket` as the `token` query param — identity
 * is derived server-side, so the former client-asserted `user_id` param is
 * gone. A FRESH ticket is fetched for every connection attempt (a reconnect
 * must never replay a consumed ticket).
 */
export class WritingSessionSocket {
  private ws: WebSocket | null = null;
  private closed = false;
  private reconnectAttempts = 0;
  private readonly maxReconnectAttempts: number;
  private readonly reconnectBaseDelayMs: number;
  private sessionId: string | undefined;
  private pendingRecover = false;

  constructor(
    private readonly chapterId: string,
    private readonly onMessage: (msg: SessionResponse) => void,
    private readonly onError: () => void,
    private readonly ticketProvider: () => Promise<string>,
    private readonly novelId?: string,
    private readonly mode?: string,
    socketOptions?: WritingSessionSocketOptions,
    initialSessionId?: string,
  ) {
    this.maxReconnectAttempts =
      socketOptions?.maxReconnectAttempts ?? DEFAULT_MAX_RECONNECT_ATTEMPTS;
    this.reconnectBaseDelayMs =
      socketOptions?.reconnectBaseDelayMs ?? DEFAULT_RECONNECT_BASE_DELAY_MS;
    this.sessionId = initialSessionId;
  }

  /** Open the WebSocket connection. Safe to call multiple times. */
  connect(): void {
    if (this.closed) return;
    void this.connectWithFreshTicket();
  }

  /**
   * Fetch a fresh single-use ticket, then open the socket (ADR-084).
   *
   * The ticket is minted per attempt — every (re)connect re-enters here, so
   * a consumed ticket is never replayed. A ticket-fetch failure surfaces
   * through `onError` (RULE-11 honest — there is no unauthenticated
   * fallback) and aborts the attempt without scheduling a reconnect.
   */
  private async connectWithFreshTicket(): Promise<void> {
    let token: string;
    try {
      token = await this.ticketProvider();
    } catch {
      this.onError();
      return;
    }
    // close() may have run while the ticket request was in flight.
    if (this.closed) return;

    const protocol =
      typeof window !== "undefined" && window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = typeof window !== "undefined" ? window.location.host : "localhost";

    const params = new URLSearchParams();
    params.set("token", token);
    if (this.novelId) params.set("project_id", this.novelId);
    if (this.mode) params.set("mode", this.mode);
    if (this.sessionId) params.set("session_id", this.sessionId);

    const url = `${protocol}//${host}/api/v1/writing/sessions/${this.chapterId}?${params.toString()}`;

    try {
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        if (!this.pendingRecover || !this.sessionId) return;
        this.send({ type: "recover_session", session_id: this.sessionId });
        this.pendingRecover = false;
      };

      this.ws.onmessage = (event: MessageEvent) => {
        try {
          const msg = JSON.parse(event.data) as SessionResponse;
          if ((msg.type === "greeting" || msg.type === "session_recovered") && msg.session_id) {
            this.sessionId = msg.session_id;
          }
          this.onMessage(msg);
        } catch {
          // Ignore malformed messages
        }
      };

      this.ws.onerror = () => {
        this.onError();
      };

      this.ws.onclose = () => {
        if (!this.closed && this.reconnectAttempts < this.maxReconnectAttempts) {
          if (this.sessionId) this.pendingRecover = true;
          this.reconnectAttempts++;
          setTimeout(() => this.connect(), this.reconnectBaseDelayMs * this.reconnectAttempts);
        }
      };
    } catch {
      // WebSocket not available (e.g. test environment) — degrade gracefully
    }
  }

  /** Send a JSON message over the socket. No-op if not connected. */
  send(message: Record<string, unknown>): void {
    try {
      this.ws?.send(JSON.stringify(message));
    } catch {
      // Silently ignore if not connected
    }
  }

  /** Close the socket and prevent further reconnection attempts. */
  close(): void {
    this.closed = true;
    this.reconnectAttempts = this.maxReconnectAttempts;
    try {
      this.ws?.close();
    } catch {
      // Silently ignore
    }
    this.ws = null;
  }
}
