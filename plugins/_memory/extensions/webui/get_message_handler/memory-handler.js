import { drawMessageToolSimple } from "/js/messages.js";

export default async function registerMemoryHandler(extData) {
  if (extData?.type === "memory") {
    extData.handler = (log) =>
      drawMessageToolSimple({ ...log, code: "MEM" });
  }
}
