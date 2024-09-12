export interface IDelay {
    apply: () => Promise<unknown>;
    setAttemptNumber: (attempt: number) => void;
}
