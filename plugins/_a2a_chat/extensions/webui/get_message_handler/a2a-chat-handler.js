import { drawMessageToolSimple } from "/js/messages.js";

export default async function registerA2AChatHandler(extData) {
  if (extData?.type === "a2a_chat") {
    extData.handler = (log) =>
      drawMessageToolSimple({ ...log, code: "A2A" });
  }
}
