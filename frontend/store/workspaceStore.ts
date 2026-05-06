"use client";

import { create } from "zustand";

interface WorkspaceStore {
  composerValue: string;
  selectedLane: string;
  setComposerValue: (value: string) => void;
  setSelectedLane: (lane: string) => void;
}

export const useWorkspaceStore = create<WorkspaceStore>((set) => ({
  composerValue: "",
  selectedLane: "drafting",
  setComposerValue: (composerValue) => set({ composerValue }),
  setSelectedLane: (selectedLane) => set({ selectedLane }),
}));
