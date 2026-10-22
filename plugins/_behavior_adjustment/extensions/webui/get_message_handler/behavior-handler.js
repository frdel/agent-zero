import { drawMessageToolSimple } from "/js/messages.js";

export default async function registerBehaviorHandler(extData) {
  if (extData?.type === "behavior_adjustment") {
    extData.handler = (log) =>
      drawMessageToolSimple({ ...log, code: "BEH" });
  }
}
