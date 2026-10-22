import { drawMessageToolSimple } from "/js/messages.js";

export default async function registerNotifyUserHandler(extData) {
  if (extData?.type === "notify_user") {
    extData.handler = (log) =>
      drawMessageToolSimple({ ...log, code: "NTF" });
  }
}
