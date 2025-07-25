### browser_open:

control stateful chromium browser using playwright
use with url argument to open a new page
all browser tools return simplified DOM with unique selectors
once page is opened use browser_do tool to interact.

```json
{
  "thoughts": ["I need to send..."],
  "tool_name": "browser_open",
  "tool_args": {
    "url": "https://www.example.com"
  }
}
```

### browser_do:

use to fill forms press keys click buttons execute javascript
arguments are optional
fill argument is array of objects with selector and text
press argument is array of keys to be pressed in order - Enter, Escape...
click argument is an array of selectors clicked in order
execute argument is a string of javascript executed
always prefer clicking on <a> or <button> tags first
confirm fields with Enter or find submit button
consents and popups may block page, close them
only use selectors mentioned in last browser response
do not repeat same steps if do not work! find ways around problems
```json
{
  "thoughts": [
    "Login required...",
    "I will fill username, password, click remember me and submit."
  ],
  "tool_name": "browser_do",
  "tool_args": {
    "fill": [
      {
        "selector": "12l",
        "text": "root"
      },
      {
        "selector": "14vs",
        "text": "toor"
      }
    ],
    "click": ["19c", "65d"]
  }
}
```

```json
{
  "thoughts": [
    "Search for...",
    "I will fill search box and press Enter."
  ],
  "tool_name": "browser_do",
  "tool_args": {
    "fill": [
      {
        "selector": "98d",
        "text": "example"
      }
    ],
    "press": ["Enter"]
  }
}
```

```json
{
  "thoughts": [
    "Standard interaction not possible, I need to execute custom code..."
  ],
  "tool_name": "browser_do",
  "tool_args": {
    "execute": "const elem = document.querySelector('[data-uid=\"4z\"]'); elem.click();"
  }
}
```
