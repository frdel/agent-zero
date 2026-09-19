import { drawMessageToolSimple } from "/js/messages.js";

export default async function registerSearchEngineHandler(extData) {
  if (extData?.tool_name === "search_engine") {
    extData.handler = (args) =>
      drawMessageToolSimple({ ...args, code: "WEB" });
  }
}
