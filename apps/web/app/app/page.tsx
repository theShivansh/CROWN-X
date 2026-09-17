import type { Metadata } from "next";
import { Suspense } from "react";

import { WorkspaceScreen } from "@/components/workspace/workspace-screen";

export const metadata: Metadata = { title: "Workspace · CROWN-X" };

// The workspace ID is in `?ws=` (static export can't pre-render unknown dynamic segments), so the
// screen reads it on the client inside a Suspense boundary.
export default function WorkspacePage() {
  return (
    <Suspense fallback={<div className="min-h-dvh bg-bg" />}>
      <WorkspaceScreen />
    </Suspense>
  );
}
