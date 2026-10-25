export type Document = { id: number; filename: string; status: string; error?: string; folder?: string };
export type Conversation = { id: number; title: string; source: string; updated_at: string };
export type AppState = {
  greeting: string;
  hotkey_label: string;
  documents: Document[];
  conversations: Conversation[];
  session_open: boolean;
  recap_pending: boolean;
};

type Signal<T> = { connect: (callback: (value: T) => void) => void; disconnect?: (callback: (value: T) => void) => void };
export type GeraldBridge = {
  state: (callback: (json: string) => void) => void;
  stateChanged: Signal<string>;
  modeChanged: Signal<string>;
  answer: Signal<string>;
  answerError: Signal<string>;
  recapReady: Signal<string>;
  agentStatus?: Signal<string>;
  setMode: (mode: string) => void;
  ask: (question: string) => void;
  documentText: (id: number, callback: (text: string) => void) => void;
  messages: (id: number, callback: (json: string) => void) => void;
  addDocuments: () => void;
  deleteDocument: (id: number) => void;
  openBoard: (title: string, lines: string) => void;
  openTd: () => void;
  endSession: () => void;
  openRecap: (path: string) => void;
  requestFocus: (active: boolean) => void;
  quit: () => void;
};

declare global {
  interface Window {
    bridge?: GeraldBridge;
    qt?: { webChannelTransport: unknown };
    QWebChannel?: new (transport: unknown, ready: (channel: { objects: { bridge: GeraldBridge } }) => void) => void;
  }
}

const mockSignal = <T,>(): Signal<T> => ({ connect: () => undefined });
const mock: GeraldBridge = {
  state: cb => cb(JSON.stringify({
    greeting: "Bonjour.", hotkey_label: "CTRL + SHIFT", documents: [],
    conversations: [], session_open: false, recap_pending: false
  })),
  stateChanged: mockSignal<string>(), modeChanged: mockSignal<string>(),
  answer: mockSignal<string>(), answerError: mockSignal<string>(), recapReady: mockSignal<string>(),
  setMode: () => undefined, ask: () => undefined, messages: (_id, cb) => cb("[]"), documentText: (_id, cb) => cb(""),
  addDocuments: () => undefined, deleteDocument: () => undefined, openBoard: () => undefined, openTd: () => undefined,
  endSession: () => undefined, openRecap: () => undefined, requestFocus: () => undefined,
  quit: () => undefined
};

export function getBridge(): GeraldBridge {
  if (window.bridge) return window.bridge;
  if (window.qt && window.QWebChannel) {
    new window.QWebChannel(window.qt.webChannelTransport, channel => {
      window.bridge = channel.objects.bridge;
      window.dispatchEvent(new Event("gerald-bridge-ready"));
    });
  }
  return new Proxy(mock, {
    get(target, property: keyof GeraldBridge) {
      return window.bridge?.[property] ?? target[property];
    }
  });
}
