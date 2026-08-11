export type SessionHistoryRole = "user" | "assistant";

export interface SessionHistoryEntry {
  readonly role: SessionHistoryRole;
  readonly text: string;
}

const MAX_ENTRIES = 20;
const MAX_ENTRY_CHARACTERS = 4_000;

export class EphemeralSessionHistory {
  private entries: SessionHistoryEntry[] = [];

  append(role: SessionHistoryRole, text: string): readonly SessionHistoryEntry[] {
    const normalized = validateEntry(role, text);
    this.entries.push(normalized);
    if (this.entries.length > MAX_ENTRIES) {
      this.entries.splice(0, this.entries.length - MAX_ENTRIES);
    }
    return this.snapshot();
  }

  clear(): void {
    this.entries = [];
  }

  snapshot(): readonly SessionHistoryEntry[] {
    return Object.freeze(this.entries.map((entry) => Object.freeze({ ...entry })));
  }
}

export class SessionHistoryView {
  private readonly list: HTMLOListElement;
  private readonly count: HTMLElement;

  constructor(private readonly host: HTMLElement) {
    host.innerHTML = `
      <details class="session-history-details">
        <summary>
          <span>Conversation</span>
          <span class="session-history-count" data-history-count>0</span>
        </summary>
        <ol class="session-history-list" data-history-list></ol>
      </details>
    `;
    const list = host.querySelector<HTMLOListElement>("[data-history-list]");
    const count = host.querySelector<HTMLElement>("[data-history-count]");
    if (list === null || count === null) {
      throw new Error("Session history view failed to mount");
    }
    this.list = list;
    this.count = count;
  }

  render(entries: readonly SessionHistoryEntry[]): void {
    this.list.replaceChildren();
    this.count.textContent = String(entries.length);
    for (const entry of entries) {
      const item = document.createElement("li");
      item.className = `session-history-entry session-history-${entry.role}`;
      const role = document.createElement("span");
      role.className = "session-history-role";
      role.textContent = entry.role === "user" ? "You" : "Ghost";
      const text = document.createElement("p");
      text.textContent = entry.text;
      item.append(role, text);
      this.list.append(item);
    }
  }

  clear(): void {
    this.render([]);
  }
}

function validateEntry(role: SessionHistoryRole, text: string): SessionHistoryEntry {
  if (role !== "user" && role !== "assistant") {
    throw new Error("Session history role is invalid");
  }
  if (
    typeof text !== "string"
    || text.trim() === ""
    || text.length > MAX_ENTRY_CHARACTERS
    || text.includes("\u0000")
  ) {
    throw new Error("Session history text is invalid");
  }
  return Object.freeze({ role, text });
}
