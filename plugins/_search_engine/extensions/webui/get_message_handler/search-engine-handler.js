import { drawMessageToolSimple } from "/js/messages.js";

export default async function registerSearchEngineHandler(extData) {
  if (extData?.type === "search_engine") {
    extData.handler = (log) =>
      drawMessageToolSimple({ ...log, code: "SRC" });
  }
}
