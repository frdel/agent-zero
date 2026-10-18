import { drawMessageToolSimple } from "/js/messages.js";

export default async function registerComputerUseHandler(extData) {
  if (extData?.type === "computer_use_remote") {
    extData.handler = (log) =>
      drawMessageToolSimple({ ...log, code: "DSK" });
  }
}
