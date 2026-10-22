import { drawMessageToolSimple } from "/js/messages.js";

export default async function registerSchedulerHandler(extData) {
  if (extData?.type === "scheduler") {
    extData.handler = (log) =>
      drawMessageToolSimple({ ...log, code: "SCH" });
  }
}
