import { drawMessageToolSimple } from "/js/messages.js";

export default async function registerWaitHandler(extData) {
  if (["wait", "progress"].includes(extData?.type)) {
    extData.handler = (log) =>
      drawMessageToolSimple({ ...log, code: "HLD" });
  }
}
