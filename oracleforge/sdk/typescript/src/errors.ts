/**
 * MAXIA Oracle SDK — typed exception hierarchy.
 *
 * All SDK calls throw a subclass of `MaxiaOracleError` on failure. Callers
 * can catch the base class to handle any failure, or catch specific
 * subclasses for typed error handling.
 *
 * Data feed only. Not investment advice. No custody. No KYC.
 */

export class MaxiaOracleError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "MaxiaOracleError";
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export class MaxiaOracleAuthError extends MaxiaOracleError {
  constructor(message: string) {
    super(message);
    this.name = "MaxiaOracleAuthError";
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export class MaxiaOracleRateLimitError extends MaxiaOracleError {
  readonly retryAfterSeconds: number | null;
  readonly limit: number | null;

  constructor(
    message: string,
    opts: { retryAfterSeconds?: number | null; limit?: number | null } = {},
  ) {
    super(message);
    this.name = "MaxiaOracleRateLimitError";
    this.retryAfterSeconds = opts.retryAfterSeconds ?? null;
    this.limit = opts.limit ?? null;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export class MaxiaOraclePaymentRequiredError extends MaxiaOracleError {
  readonly accepts: unknown[];

  constructor(message: string, accepts: unknown[] = []) {
    super(message);
    this.name = "MaxiaOraclePaymentRequiredError";
    this.accepts = accepts;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export class MaxiaOracleValidationError extends MaxiaOracleError {
  constructor(message: string) {
    super(message);
    this.name = "MaxiaOracleValidationError";
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export class MaxiaOracleUpstreamError extends MaxiaOracleError {
  constructor(message: string) {
    super(message);
    this.name = "MaxiaOracleUpstreamError";
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export class MaxiaOracleTransportError extends MaxiaOracleError {
  constructor(message: string) {
    super(message);
    this.name = "MaxiaOracleTransportError";
    Object.setPrototypeOf(this, new.target.prototype);
  }
}
