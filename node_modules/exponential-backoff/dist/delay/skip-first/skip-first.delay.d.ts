import { Delay } from "../delay.base";
export declare class SkipFirstDelay extends Delay {
    apply(): Promise<unknown>;
    private readonly isFirstAttempt;
    protected readonly numOfDelayedAttempts: number;
}
