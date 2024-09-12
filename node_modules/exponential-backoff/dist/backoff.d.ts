import { IBackOffOptions, BackoffOptions } from "./options";
export { BackoffOptions, IBackOffOptions };
export declare function backOff<T>(request: () => Promise<T>, options?: BackoffOptions): Promise<T>;
