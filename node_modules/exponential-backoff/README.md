# exponential-backoff

A utility that allows retrying a function with an exponential delay between attempts.

## Installation

```
npm i exponential-backoff
```

## Usage

The `backOff<T>` function takes a promise-returning function to retry, and an optional `BackOffOptions` object. It returns a `Promise<T>`.

```ts
function backOff<T>(
  request: () => Promise<T>,
  options?: BackOffOptions
): Promise<T>;
```

Here is an example retrying a function that calls a hypothetical weather endpoint:

```js
import { backOff } from "exponential-backoff";

function getWeather() {
  return fetch("weather-endpoint");
}

async function main() {
  try {
    const response = await backOff(() => getWeather());
    // process response
  } catch (e) {
    // handle error
  }
}

main();
```

Migrating across major versions? Here are our [breaking changes](https://github.com/coveo/exponential-backoff/tree/master/doc/migration-guide.md).

### `BackOffOptions`

- `delayFirstAttempt?: boolean`

  Decides whether the `startingDelay` should be applied before the first call. If `false`, the first call will occur without a delay.

  Default value is `false`.

- `jitter?: JitterType | string`

  Decides whether a [jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/) should be applied to the delay. Possible values are `full` and `none`.

  Default value is `none`.

- `maxDelay?: number`

  The maximum delay, in milliseconds, between two consecutive attempts.

  Default value is `Infinity`.

- `numOfAttempts?: number`

  The maximum number of times to attempt the function.

  Default value is `10`.

  Minimum value is `1`.

- `retry?: (e: any, attemptNumber: number) => boolean | Promise<boolean>`

  The `retry` function can be used to run logic after every failed attempt (e.g. logging a message, assessing the last error, etc.). It is called with the last error and the upcoming attempt number. Returning `true` will retry the function as long as the `numOfAttempts` has not been exceeded. Returning `false` will end the execution.

  Default value is a function that always returns `true`.

- `startingDelay?: number`

  The delay, in milliseconds, before executing the function for the first time.

  Default value is `100` ms.

- `timeMultiple?: number`

  The `startingDelay` is multiplied by the `timeMultiple` to increase the delay between reattempts.

  Default value is `2`.
