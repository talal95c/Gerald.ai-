export const demoEvents = ["notes-open", "documents-open", "td-open", "turn-done", "board-open", "ink"] as const;
export type DemoEvent = typeof demoEvents[number];
export type DemoFocusTarget = "documents" | "td4" | null;
export type DemoStage = 1 | 2 | 3 | 4 | 5;

type DemoEventMessage = {type: "gerald-demo"; event: DemoEvent; stage?: DemoStage};
type DemoAskMessage = {type: "gerald-demo-ask"; text: string; stage: DemoStage};
type DemoFocusMessage = {type: "gerald-demo-focus"; target: Exclude<DemoFocusTarget, null> | null; stage: DemoStage};

export const demoMode = new URLSearchParams(location.search).get("demo") === "1";

const isDemoStage = (value: unknown): value is DemoStage => value === 1 || value === 2 || value === 3 || value === 4 || value === 5;

export function postDemoEvent(event: DemoEvent, stage?: DemoStage) {
  if (!demoMode) return;
  const message = {type: "gerald-demo", event, ...(stage === undefined ? {} : {stage})};
  if (window.parent === window) {
    window.postMessage(message, location.origin);
    return;
  }
  window.parent.postMessage(message, location.origin);
}

export function isDemoEventMessage(event: MessageEvent<unknown>): event is MessageEvent<DemoEventMessage> {
  if (event.origin !== location.origin || !event.data || typeof event.data !== "object") return false;
  const data = event.data as Partial<DemoEventMessage>;
  return data.type === "gerald-demo" && typeof data.event === "string" && demoEvents.includes(data.event as DemoEvent)
    && (data.stage === undefined || isDemoStage(data.stage))
    && (data.event !== "turn-done" || isDemoStage(data.stage));
}

export function isDemoAskMessage(event: MessageEvent<unknown>): event is MessageEvent<DemoAskMessage> {
  if (event.origin !== location.origin || !event.data || typeof event.data !== "object") return false;
  const data = event.data as Partial<DemoAskMessage>;
  return data.type === "gerald-demo-ask" && typeof data.text === "string" && data.text.trim().length > 0 && isDemoStage(data.stage);
}

export function isDemoFocusMessage(event: MessageEvent<unknown>): event is MessageEvent<DemoFocusMessage> {
  if (event.origin !== location.origin || !event.data || typeof event.data !== "object") return false;
  const data = event.data as Partial<DemoFocusMessage>;
  return data.type === "gerald-demo-focus" && (data.target === null || data.target === "documents" || data.target === "td4") && isDemoStage(data.stage);
}
