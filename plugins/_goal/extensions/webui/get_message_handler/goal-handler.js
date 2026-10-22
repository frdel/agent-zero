import { drawMessageToolSimple } from "/js/messages.js";

export default async function registerGoalHandler(extData) {
  if (extData?.type === "goal") {
    extData.handler = (log) =>
      drawMessageToolSimple({ ...log, code: "AIM" });
  }
}
