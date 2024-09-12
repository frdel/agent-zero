import { IBackOffOptions } from "../options";
export declare type Jitter = (delay: number) => number;
export declare function JitterFactory(options: IBackOffOptions): Jitter;
