/**
 * Minimal structural typing for the ElizaOS plugin surface.
 *
 * We deliberately do NOT import from `@elizaos/core` at build time to keep
 * the plugin compilable without the host runtime installed. TypeScript
 * structural typing does the rest — at install time the user already has
 * `@elizaos/core` in their project, and the shapes defined below line up
 * 1-1 with the framework's `Plugin` / `Action` / `Memory` interfaces.
 *
 * If the host runtime changes its shape in a breaking way, these
 * interfaces are the single place to update.
 */

export interface IAgentRuntime {
  /**
   * Read a runtime setting — character-defined, env-overridden. ElizaOS
   * implementations may return `undefined` (or `null`) for unknown keys.
   */
  getSetting(key: string): string | undefined | null;
}

export interface Content {
  text?: string;
  [key: string]: unknown;
}

export interface Memory {
  content: Content;
  [key: string]: unknown;
}

export type State = Record<string, unknown>;

export type HandlerCallback = (payload: {
  text: string;
  content?: Record<string, unknown>;
}) => void | Promise<void>;

export interface ActionExample {
  user: string;
  content: Content;
}

export interface Action {
  name: string;
  similes?: string[];
  description: string;
  validate: (
    runtime: IAgentRuntime,
    message: Memory,
    state?: State,
  ) => Promise<boolean>;
  handler: (
    runtime: IAgentRuntime,
    message: Memory,
    state?: State,
    options?: Record<string, unknown>,
    callback?: HandlerCallback,
  ) => Promise<boolean>;
  examples?: ActionExample[][];
}

export interface Plugin {
  name: string;
  description: string;
  actions: Action[];
}
