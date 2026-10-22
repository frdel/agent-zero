import {
  cleanStepTitle,
  drawProcessStep,
} from "/js/messages.js";

export default async function registerOfficeArtifactHandler(extData) {
  if (extData?.tool_name === "office_artifact") {
    extData.handler = drawOfficeArtifactTool;
  }
}

function drawOfficeArtifactTool({
  id,
  type,
  heading,
  content,
  kvps,
  timestamp,
  agentno = 0,
  ...additional
}) {
  const args = arguments[0];
  const title = cleanStepTitle(heading);
  const displayKvps = { ...kvps };
  delete displayKvps._tool_name;

  return drawProcessStep({
    id,
    title,
    code: "OFF",
    classes: undefined,
    kvps: displayKvps,
    content,
    actionButtons: [],
    log: args,
  });
}
