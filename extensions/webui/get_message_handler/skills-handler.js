import { drawMessageToolSimple } from "/js/messages.js";

export default async function registerSkillsHandler(extData) {
  if (extData?.type === "skills_tool") {
    extData.handler = (log) =>
      drawMessageToolSimple({ ...log, code: "SKL" });
  }
}
