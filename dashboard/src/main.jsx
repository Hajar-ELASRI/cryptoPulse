import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { TzProvider } from "./lib/settings";
import "./index.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <TzProvider>
        <App />
      </TzProvider>
    </BrowserRouter>
  </StrictMode>,
);
