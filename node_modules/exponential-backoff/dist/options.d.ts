export declare type JitterType = "none" | "full";
export declare type BackoffOptions = Partial<IBackOffOptions>;
export interface IBackOffOptions {
    delayFirstAttempt: boolean;
    jitter: JitterType;
    maxDelay: number;
    numOfAttempts: number;
    retry: (e: any, attemptNumber: number) => boolean | Promise<boolean>;
    startingDelay: number;
    timeMultiple: number;
}
export declare function getSanitizedOptions(options: BackoffOptions): IBackOffOptions;
