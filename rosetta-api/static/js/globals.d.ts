// Ambient declarations for the browser globals this frontend defines or relies on.
//
// The JS files load as plain <script> tags sharing one global scope, so cross-file
// references are globals rather than imports. state.js publishes its two accessors on
// window; declaring them here is what lets `tsc --checkJs` see them.

/** Mutate application state. The only sanctioned way to write to the store. */
declare function dispatch(action: string, payload?: any): void;

/** Read application state. Treat the result as read-only. */
declare function getState(): {
  authToken: string | null;
  isProcessing: boolean;
  currentSuiteData: any;
  currentSuiteTitle: string;
  batchQueue: any[];
  allAlgorithms: any[];
  currentAlgoName: string;
  currentRunnerConfig: Record<string, any>;
  currentJobId: string | null;
  currentHistoryRunId: string | null;
  maxQubitsStatevector: number;
  maxQubitsMeasured: number;
  maxRunsPerRunner: number;
  maxTotalRuns: number;
  executionMode: string;
};

interface Window {
  dispatch: typeof dispatch;
  getState: typeof getState;
  /** File System Access API, used by the opt-in autosave. Not in every browser. */
  showDirectoryPicker?: (options?: any) => Promise<any>;
}
