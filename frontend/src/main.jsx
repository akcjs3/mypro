import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css"; // tailwind 쓴다면 이 줄 유지

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
