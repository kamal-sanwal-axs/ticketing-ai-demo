import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";

const input = window.__SANDBOX_INPUT__ || {};
createRoot(document.getElementById("root")).render(<App input={input} />);
