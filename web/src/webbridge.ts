import type { AppState, Document, GeraldBridge } from "./bridge";
import linearFunctions from "../../gerald/home/demo_docs/fonctions-affines.md?raw";
import polynomials from "../../gerald/home/demo_docs/polynomes.md?raw";
import method from "../../gerald/home/demo_docs/methode.md?raw";
import td4 from "../../gerald/home/demo_docs/td-4.md?raw";

export type WebDocument = {
  id: number;
  filename: string;
  mime: string;
  blob?: Blob;
  content?: string;
  folder: string;
  created_at: string;
};

const builtins: WebDocument[] = [
  {id: -1, filename: "Fonctions affines.md", mime: "text/markdown", content: linearFunctions, folder: "Maths — Second degré", created_at: ""},
  {id: -2, filename: "Polynômes du second degré.md", mime: "text/markdown", content: polynomials, folder: "Maths — Second degré", created_at: ""},
  {id: -3, filename: "Fiche méthode — trinôme.md", mime: "text/markdown", content: method, folder: "Maths — Second degré", created_at: ""},
  {id: -4, filename: "TD 4 — Polynômes du second degré.md", mime: "text/markdown", content: td4, folder: "Maths — Second degré", created_at: ""},
];
const demoMode = new URLSearchParams(location.search).get("demo") === "1";
const listeners = new Set<(value: string) => void>();
let uploadError = "";
let database: Promise<IDBDatabase> | null = null;

function openDatabase() {
  if (database) return database;
  database = new Promise((resolve, reject) => {
    const request = indexedDB.open("gerald", 1);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains("documents")) {
        request.result.createObjectStore("documents", {keyPath: "id", autoIncrement: true});
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
  return database;
}

function readUploads(): Promise<WebDocument[]> {
  return openDatabase().then(db => new Promise((resolve, reject) => {
    const request = db.transaction("documents", "readonly").objectStore("documents").getAll();
    request.onsuccess = () => resolve(request.result as WebDocument[]);
    request.onerror = () => reject(request.error);
  }));
}

async function emitState() {
  const uploads = await readUploads().catch(() => []);
  const documents: Document[] = [
    ...(demoMode ? builtins.map(({id, filename, mime, folder, created_at}) => ({id, filename, mime, folder, created_at, status: "ready", builtin: true})) : []),
    ...uploads.map(({id, filename, mime, folder, created_at}) => ({id, filename, mime, folder, created_at, status: "ready"})),
  ];
  const state: AppState & {recaps: []; upload_error: string} = {
    greeting: "Bonjour.",
    hotkey_label: "CTRL + SHIFT",
    documents,
    conversations: [],
    session_open: false,
    recap_pending: false,
    last_exercise: null,
    recaps: [],
    upload_error: uploadError,
  };
  const json = JSON.stringify(state);
  listeners.forEach(listener => listener(json));
  return json;
}

function mimeFor(file: File) {
  if (file.type) return file.type;
  return ({pdf: "application/pdf", png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg", webp: "image/webp"} as Record<string, string>)[file.name.split(".").pop()?.toLowerCase() ?? ""] ?? "application/octet-stream";
}

async function saveFile(file: File) {
  const db = await openDatabase();
  await new Promise<void>((resolve, reject) => {
    const request = db.transaction("documents", "readwrite").objectStore("documents").add({
      filename: file.name,
      mime: mimeFor(file),
      blob: file,
      folder: "Mes documents",
      created_at: new Date().toISOString(),
    });
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

function addDocuments() {
  const input = document.createElement("input");
  input.type = "file";
  input.multiple = true;
  input.accept = ".pdf,.png,.jpg,.jpeg,.webp";
  input.hidden = true;
  input.onchange = () => {
    void (async () => {
      const files = [...(input.files ?? [])];
      const rejected = files.filter(file => file.size > 25 * 1024 * 1024);
      uploadError = rejected.length
        ? `${rejected.map(file => file.name).join(", ")} dépasse la limite de 25 Mo.`
        : "";
      for (const file of files) {
        if (file.size > 25 * 1024 * 1024) continue;
        try {
          await saveFile(file);
        } catch {
          uploadError = `Impossible d’enregistrer ${file.name}.`;
        }
      }
      await emitState();
      input.remove();
    })();
  };
  input.oncancel = () => input.remove();
  document.body.append(input);
  input.click();
}

export async function loadWebDocument(id: number): Promise<WebDocument | null> {
  const builtin = builtins.find(document => document.id === id);
  if (builtin) return builtin;
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const request = db.transaction("documents", "readonly").objectStore("documents").get(id);
    request.onsuccess = () => resolve((request.result as WebDocument | undefined) ?? null);
    request.onerror = () => reject(request.error);
  });
}

function parseLines(value: string) {
  try {
    const lines = JSON.parse(value);
    return Array.isArray(lines) ? lines.map(String) : [];
  } catch {
    return [];
  }
}

const emptyState: AppState = {
  greeting: "Bonjour.",
  hotkey_label: "CTRL + SHIFT",
  documents: [],
  conversations: [],
  session_open: false,
  recap_pending: false,
  last_exercise: null,
};
const stateChanged = {
  connect: (callback: (value: string) => void) => listeners.add(callback),
  disconnect: (callback: (value: string) => void) => listeners.delete(callback),
};

export const webBridge: GeraldBridge = {
  state: callback => { void emitState().then(callback); },
  stateChanged,
  modeChanged: {connect: () => undefined},
  answer: {connect: () => undefined},
  answerError: {connect: () => undefined},
  recapReady: {connect: () => undefined},
  setMode: () => undefined,
  ask: () => undefined,
  documentText: (_id, callback) => callback(""),
  messages: (_id, callback) => callback("[]"),
  addDocuments,
  deleteDocument: id => {
    if (id < 0) return;
    void openDatabase().then(db => new Promise<void>((resolve, reject) => {
      const request = db.transaction("documents", "readwrite").objectStore("documents").delete(id);
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    })).then(() => emitState());
  },
  openBoard: (title, lines) => window.dispatchEvent(new CustomEvent("gerald-open-board", {detail: {title, lines: parseLines(lines)}})),
  openTd: () => window.dispatchEvent(new CustomEvent("gerald-open-document", {detail: {id: -4}})),
  endSession: () => undefined,
  openRecap: () => undefined,
  requestFocus: () => undefined,
  quit: () => window.location.assign("/landing.html"),
  openDocument: id => window.dispatchEvent(new CustomEvent("gerald-open-document", {detail: {id}})),
};

export function webAppState() {
  return emitState().catch(() => JSON.stringify(emptyState));
}
