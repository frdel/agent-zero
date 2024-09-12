import { IBackOffOptions } from "../options";
import { IDelay } from "./delay.interface";
export declare function DelayFactory(options: IBackOffOptions, attempt: number): IDelay;
