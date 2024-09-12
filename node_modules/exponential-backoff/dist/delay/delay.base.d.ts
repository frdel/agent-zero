import { IDelay } from "./delay.interface";
import { IBackOffOptions } from "../options";
export declare abstract class Delay implements IDelay {
    private options;
    protected attempt: number;
    constructor(options: IBackOffOptions);
    apply(): Promise<unknown>;
    setAttemptNumber(attempt: number): void;
    private readonly jitteredDelay;
    private readonly delay;
    protected readonly numOfDelayedAttempts: number;
}
