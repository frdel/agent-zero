/** Async function that waits for specified number of time units. */
export async function sleep(miliseconds = 0, seconds = 0, minutes = 0, hours = 0, days = 0) {
    hours += days * 24;
    minutes += hours * 60;
    seconds += minutes * 60;
    miliseconds += seconds * 1000;
    await new Promise((resolve) => setTimeout(resolve, miliseconds));
  }
  export default sleep;
  
  /** Equals to Sleep(0), but can be used to yield break a coroutine after N interations. */
  let yieldIterations = 0;
  export async function Yield(afterIterations = 1) {
    yieldIterations++;
    if (yieldIterations >= afterIterations) {
      await new Promise((resolve) => setTimeout(resolve, 0));
      yieldIterations = 0;
    }
  }
  
  /** Awaits equivalent of Sleep(0) N times which means it skips N-1 turns in the eventQueue.  */
  export async function Skip(turns = 1) {
    while (turns > 0) {
      await new Promise((resolve) => setTimeout(resolve, 0));
      turns--;
    }
  }