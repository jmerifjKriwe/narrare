import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { adoptStoredFormality } from "./lib/formality";
import { queryClient } from "./lib/query";
import { router } from "./router";

// The register is a local choice, read once before the first paint. The
// language itself waits for the server row in the shell; this one has no row.
adoptStoredFormality();

const container = document.getElementById("root");
if (container === null) {
  // index.html owns the mount point; without it nothing can render, and a
  // silent return would show a blank page with no error anywhere.
  throw new Error("index.html is missing #root");
}

createRoot(container).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
