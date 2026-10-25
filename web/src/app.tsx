import React, { useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
import { mountNotch } from "./notch";
import {useCompanion} from "./companion";
import "./app.css";

function App() {
  const notch = useRef<HTMLDivElement>(null);
  const companion = useCompanion();

  useEffect(() => {
    if (notch.current) mountNotch(notch.current);
  }, []);

  return <main className="app-root">
    {companion.src && <iframe
      key={companion.src}
      ref={companion.frame}
      className="app-frame"
      title="Gerald"
      src={companion.src}
      allow="microphone; autoplay"
      onLoad={companion.onFrameLoad}
    />}
    <div className="app-notch-host" ref={notch}/>
  </main>;
}

document.body.classList.add("app-page");
createRoot(document.getElementById("root")!).render(<App/>);
