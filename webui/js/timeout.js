// function timeout(ms: number, errorMessage: string = "Operation timed out") {
//   let timeoutId: number;
//   const promise = new Promise<never>((_, reject) => {
//     timeoutId = setTimeout(() => {
//       reject(new Error(errorMessage));
//     }, ms);
//   });
//   return { promise, cancel: () => clearTimeout(timeoutId) };
// }

// export async function Timeout<T>(promise: Promise<T>, ms: number): Promise<T> {
//   const { promise: timeoutPromise, cancel: cancelTimeout } = timeout(ms);

//   // Race the timeout against the original promise
//   return await Promise.race([promise, timeoutPromise]).finally(cancelTimeout);
// }
