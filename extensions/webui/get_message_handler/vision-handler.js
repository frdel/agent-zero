import { drawMessageToolSimple } from "/js/messages.js";

export default async function registerVisionHandler(extData) {
  if (extData?.type === "vision_load") {
    extData.handler = (log) =>
      drawMessageToolSimple({ ...log, code: "EYE" });
  }
}
